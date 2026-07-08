"""Milestone 1 — persistence round-trip for AI generation metadata.

Verifies the additive ``generation_model`` / ``generation_confidence`` columns
are persisted and reconstructed faithfully by the
:class:`~digital_twin.repository.DigitalTwinRepository`, and that fixes without
them (heuristic/report-only, and existing Milestone 0 records) round-trip with
both fields ``None`` — proving the additive migration does not disturb existing
data shapes.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from digital_twin.models import Base
from digital_twin.repository import DigitalTwinRepository

from core.types import (
    CrawledPage,
    FixStatus,
    FixType,
    Issue,
    IssueCandidate,
    IssueDetail,
    IssueType,
    Severity,
    SuggestedFix,
    TargetRef,
)

TENANT = "tenant-a"
NOW = datetime(2024, 1, 1, tzinfo=timezone.utc)


def _repo() -> DigitalTwinRepository:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    return DigitalTwinRepository(factory, tenant_id=TENANT)


def _seed_issue(repo: DigitalTwinRepository) -> str:
    """Persist a page + issue and return the issue id (FK for fixes)."""
    repo.upsert_pages(
        TENANT,
        [
            CrawledPage(
                url="https://example.com/",
                final_url="https://example.com/",
                status_code=200,
                images=[],
                crawled_at=NOW,
            )
        ],
    )
    issues = repo.persist_issues(
        TENANT,
        [
            IssueCandidate(
                issue_type=IssueType.MISSING_ALT_TEXT,
                severity=Severity.LOW,
                description="missing alt",
                detail=IssueDetail(page_url="https://example.com/"),
            )
        ],
    )
    return issues[0].id


def test_generation_metadata_round_trips() -> None:
    repo = _repo()
    issue_id = _seed_issue(repo)

    fix = SuggestedFix(
        id="fix-ai",
        tenant_id=TENANT,
        issue_id=issue_id,
        fix_type=FixType.UPDATE_ALT_TEXT,
        auto_applicable=1,
        target_ref=TargetRef(media_id=42),
        proposed_value="A red touring bicycle",
        reason="Alt text proposed by AI model 'm1'.",
        status=FixStatus.PENDING,
        generation_model="m1",
        generation_confidence=0.83,
    )
    repo.persist_fixes(TENANT, [fix])

    loaded = repo.get_fix(TENANT, "fix-ai")
    assert loaded is not None
    assert loaded.generation_model == "m1"
    assert loaded.generation_confidence == 0.83
    # And via the list read used by GET /fixes.
    listed = {f.id: f for f in repo.list_fixes(TENANT)}
    assert listed["fix-ai"].generation_model == "m1"
    assert listed["fix-ai"].generation_confidence == 0.83


def test_fix_without_generation_metadata_round_trips_as_none() -> None:
    repo = _repo()
    issue_id = _seed_issue(repo)

    fix = SuggestedFix(
        id="fix-report",
        tenant_id=TENANT,
        issue_id=issue_id,
        fix_type=None,
        auto_applicable=0,
        proposed_value=None,
        reason="Manual review required.",
        status=FixStatus.PENDING,
    )
    repo.persist_fixes(TENANT, [fix])

    loaded = repo.get_fix(TENANT, "fix-report")
    assert loaded is not None
    assert loaded.generation_model is None
    assert loaded.generation_confidence is None
