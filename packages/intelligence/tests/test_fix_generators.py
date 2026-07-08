"""M2 fix-generator tests (§9, acceptance #8).

Proves the KnowledgeObject-driven generators produce Milestone 1 SuggestedFix
records that flow through the existing Governance pipeline **unchanged**.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.types import (
    CrawledPage,
    FixStatus,
    IssueCandidate,
    IssueDetail,
    IssueType,
    Severity,
)
from digital_twin.models import Base
from digital_twin.repository import DigitalTwinRepository
from governance.service import GovernanceService
from intelligence.fixes import (
    ALL_KO_FIX_GENERATORS,
    MetaDescriptionFixGenerator,
    SchemaFixGenerator,
    SlugFixGenerator,
    TitleFixGenerator,
)
from intelligence.models.identity import IdentitySection
from intelligence.models.knowledge_object import KnowledgeObject
from intelligence.models.schema_intelligence import SchemaBlock

TENANT = "tenant-fix"


def _ko_with_proposals() -> KnowledgeObject:
    ko = KnowledgeObject(
        id="k1", page_id="p1", tenant_id=TENANT, version=1,
        identity=IdentitySection(url="https://x/p"),
    )
    ko.metadata.meta_description.proposed_value = "A great meta description for the page."
    ko.metadata.meta_description.proposed_reasoning = "Includes keyphrase."
    ko.metadata.seo_title.proposed_value = "A Great SEO Title"
    ko.identity.proposed_slug.proposed_value = "a-great-slug"
    ko.schema_intelligence.generated_jsonld = [
        SchemaBlock(type="LocalBusiness", raw_jsonld='{"@context":"https://schema.org","@type":"LocalBusiness"}')
    ]
    return ko


def test_all_four_generators_produce_report_only_fixes():
    ko = _ko_with_proposals()
    kinds = set()
    for gen_cls in ALL_KO_FIX_GENERATORS:
        fix = gen_cls().generate(ko, issue_id="issue-1")
        assert fix is not None
        assert fix.auto_applicable == 0  # M1 publisher can't write these -> report-only
        assert fix.proposed_value
        assert fix.status == FixStatus.PENDING
        kinds.add(gen_cls().kind)
    assert kinds == {"update_meta_description", "update_title", "update_slug", "update_schema"}


def test_generator_returns_none_without_proposal():
    empty = KnowledgeObject(
        id="k", page_id="p", tenant_id=TENANT, version=1,
        identity=IdentitySection(url="https://x/p"),
    )
    assert MetaDescriptionFixGenerator().generate(empty, issue_id="i") is None
    assert TitleFixGenerator().generate(empty, issue_id="i") is None
    assert SlugFixGenerator().generate(empty, issue_id="i") is None
    assert SchemaFixGenerator().generate(empty, issue_id="i") is None


def test_fix_flows_through_governance_unchanged():
    # Real M1 Digital_Twin (in-memory) + governance; a fake publisher that must
    # never be called for a report-only fix.
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    sf = sessionmaker(bind=engine, expire_on_commit=False)
    twin = DigitalTwinRepository(sf, tenant_id=TENANT)

    twin.upsert_pages(TENANT, [CrawledPage(
        url="https://x/p", final_url="https://x/p", status_code=200,
        crawled_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )])
    issue = twin.persist_issues(TENANT, [IssueCandidate(
        issue_type=IssueType.MISSING_META_DESCRIPTION, severity=Severity.MEDIUM,
        description="missing meta", detail=IssueDetail(page_url="https://x/p"),
    )])[0]

    fix = MetaDescriptionFixGenerator().generate(_ko_with_proposals(), issue_id=issue.id)
    twin.persist_fixes(TENANT, [fix])

    class _NoWritePublisher:
        def list_pages(self): return []
        def get_page(self, page_id): raise AssertionError
        def update_page_content(self, page_id, content): raise AssertionError("no write for report-only")
        def get_media(self, media_id): raise AssertionError
        def update_media_alt_text(self, media_id, alt_text): raise AssertionError("no write for report-only")

    governance = GovernanceService(twin, _NoWritePublisher())
    updated = governance.approve_fix(TENANT, fix.id, actor="alice", rationale="looks good")
    # Report-only fix approved through the existing pipeline, no publisher write.
    assert updated.status == FixStatus.APPROVED
