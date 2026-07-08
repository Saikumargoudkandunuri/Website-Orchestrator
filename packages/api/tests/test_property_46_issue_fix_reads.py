"""Property 46 — Issue and fix reads return exactly what was persisted.

Feature: website-orchestrator-milestone-0, Property 46: Issue and fix reads
return exactly what was persisted

Validates: Requirements 10.2, 10.3

Requirement 10.2: ``GET /issues`` returns the tenant's persisted issues,
excluding those marked ignored.
Requirement 10.3: ``GET /fixes`` returns *all* of the tenant's persisted
suggested fixes, regardless of status.

This property drives the API_Surface read endpoints through a FastAPI
:class:`~fastapi.testclient.TestClient` wired to a real, network-free
:class:`~digital_twin.repository.DigitalTwinRepository` backed by in-memory
SQLite (the same pattern as ``test_app_read.py``). The other subsystems are
minimal fakes that satisfy the composition root but are never invoked by these
reads.

For any generated set of persisted issues (with some marked ignored) and any
generated set of persisted fixes (varied ``fix_type`` / ``auto_applicable`` /
``status``), the property asserts:

* ``GET /issues`` returns exactly the persisted, non-ignored issues — matched by
  id, with ``issue_type`` / ``severity`` / ``description`` / ``page_url``
  preserved (Req 10.2).
* ``GET /fixes`` returns exactly the persisted fixes — matched by id, with
  ``status`` / ``auto_applicable`` / ``fix_type`` / ``issue_id`` /
  ``proposed_value`` / ``reason`` preserved (Req 10.3).
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient
from hypothesis import given, settings
from hypothesis import strategies as st
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from check_engine import CheckEngine
from digital_twin.models import Base
from digital_twin.repository import DigitalTwinRepository
from fix_generator import FixGenerator
from governance.service import GovernanceService

from core.types import (
    CrawledPage,
    FixStatus,
    FixType,
    IssueCandidate,
    IssueDetail,
    IssueType,
    Severity,
    SuggestedFix,
)

from api import create_app

TENANT = "tenant-a"
PAGE_URL = "https://example.com/"


# --- Fakes (never invoked by the read endpoints) ------------------------------


class FakeCrawler:
    """A CrawlerPort fake; never invoked by the read endpoints."""

    def crawl_site(self, start_url: str, max_pages: int):  # pragma: no cover
        raise NotImplementedError

    def check_link_status(self, url: str):  # pragma: no cover
        raise NotImplementedError


class FakePublishingAdapter:
    """Minimal PublishingAdapterPort so the Governance_Layer can be built."""

    def list_pages(self):  # pragma: no cover - unused
        return []

    def get_page(self, page_id: int):  # pragma: no cover - unused
        raise NotImplementedError

    def update_page_content(self, page_id: int, content: str):  # pragma: no cover
        raise NotImplementedError

    def get_media(self, media_id: int):  # pragma: no cover - unused
        raise NotImplementedError

    def update_media_alt_text(self, media_id: int, alt_text: str):  # pragma: no cover
        raise NotImplementedError


def _build_app():
    """Build an app wired to a fresh in-memory repo, returning ``(app, repo)``."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    repo = DigitalTwinRepository(session_factory, tenant_id=TENANT)
    governance = GovernanceService(repo, FakePublishingAdapter())

    app = create_app(
        crawler=FakeCrawler(),
        digital_twin=repo,
        check_engine=CheckEngine(),
        fix_generator=FixGenerator(),
        governance=governance,
        tenant_id=TENANT,
    )
    return app, repo


def _seed_page(repo: DigitalTwinRepository) -> None:
    """Persist a single page so issues can be attached to it."""
    now = datetime(2024, 1, 1, tzinfo=timezone.utc)
    repo.upsert_pages(
        TENANT,
        [
            CrawledPage(
                url=PAGE_URL,
                final_url=PAGE_URL,
                status_code=200,
                crawled_at=now,
            )
        ],
    )


# --- Strategies ---------------------------------------------------------------

# Non-empty, non-whitespace text for descriptions.
_nonblank = st.text(min_size=1, max_size=40).filter(lambda s: s.strip() != "")

# Free-form optional text (may be None / blank) for a fix's proposed value/reason.
_optional_text = st.one_of(st.none(), st.text(min_size=0, max_size=40))


@st.composite
def _issue_spec(draw: st.DrawFn) -> dict:
    """A varied issue candidate plus an ``ignore`` flag."""
    return {
        "issue_type": draw(st.sampled_from(list(IssueType))),
        "severity": draw(st.sampled_from(list(Severity))),
        "description": draw(_nonblank),
        "ignore": draw(st.booleans()),
    }


@st.composite
def _fix_spec(draw: st.DrawFn) -> dict:
    """A varied suggested fix (id assigned later to guarantee uniqueness)."""
    return {
        "issue_id": draw(_nonblank),
        "fix_type": draw(st.one_of(st.none(), st.sampled_from(list(FixType)))),
        "auto_applicable": draw(st.sampled_from([0, 1])),
        "proposed_value": draw(_optional_text),
        "reason": draw(_optional_text),
        "status": draw(st.sampled_from(list(FixStatus))),
    }


# --- Property -----------------------------------------------------------------


@settings(max_examples=100, deadline=None)
@given(
    issue_specs=st.lists(_issue_spec(), min_size=0, max_size=6),
    fix_specs=st.lists(_fix_spec(), min_size=0, max_size=6),
)
def test_property_46_issue_and_fix_reads_return_exactly_what_was_persisted(
    issue_specs: list[dict],
    fix_specs: list[dict],
) -> None:
    """For any persisted set of issues (some ignored) and fixes (varied shape),
    ``GET /issues`` returns exactly the non-ignored persisted issues and
    ``GET /fixes`` returns exactly all persisted fixes — matched by id and key
    fields.

    Feature: website-orchestrator-milestone-0, Property 46: Issue and fix reads
    return exactly what was persisted

    Validates: Requirements 10.2, 10.3
    """
    app, repo = _build_app()
    _seed_page(repo)

    # --- Persist the generated issues, then ignore the flagged ones -----------
    candidates = [
        IssueCandidate(
            issue_type=spec["issue_type"],
            severity=spec["severity"],
            description=spec["description"],
            detail=IssueDetail(page_url=PAGE_URL),
        )
        for spec in issue_specs
    ]
    stored_issues = repo.persist_issues(TENANT, candidates)

    # Expected active issues: those not marked ignored, keyed by their id.
    expected_active: dict[str, dict] = {}
    for spec, stored in zip(issue_specs, stored_issues):
        if spec["ignore"]:
            repo.mark_issue_ignored(TENANT, stored.id)
        else:
            expected_active[stored.id] = {
                "issue_type": spec["issue_type"].value,
                "severity": spec["severity"].value,
                "description": spec["description"],
                "page_url": PAGE_URL,
            }

    # --- Persist the generated fixes with unique ids --------------------------
    fixes = [
        SuggestedFix(
            id=f"fix-{index}",
            tenant_id=TENANT,
            issue_id=spec["issue_id"],
            fix_type=spec["fix_type"],
            auto_applicable=spec["auto_applicable"],
            proposed_value=spec["proposed_value"],
            reason=spec["reason"],
            status=spec["status"],
        )
        for index, spec in enumerate(fix_specs)
    ]
    repo.persist_fixes(TENANT, fixes)

    expected_fixes = {
        fix.id: {
            "issue_id": fix.issue_id,
            "fix_type": fix.fix_type.value if fix.fix_type else None,
            "auto_applicable": fix.auto_applicable,
            "proposed_value": fix.proposed_value,
            "reason": fix.reason,
            "status": fix.status.value,
        }
        for fix in fixes
    }

    client = TestClient(app)

    # --- GET /issues returns exactly the persisted non-ignored issues (10.2) --
    issues_response = client.get("/issues")
    assert issues_response.status_code == 200
    issues_body = issues_response.json()

    assert {i["id"] for i in issues_body} == set(expected_active)
    for item in issues_body:
        expected = expected_active[item["id"]]
        assert item["issue_type"] == expected["issue_type"]
        assert item["severity"] == expected["severity"]
        assert item["description"] == expected["description"]
        assert item["detail"]["page_url"] == expected["page_url"]
        # Active issues are never ignored (Req 10.2, 4.11).
        assert item["ignored"] is False

    # --- GET /fixes returns exactly all persisted fixes (10.3) ----------------
    fixes_response = client.get("/fixes")
    assert fixes_response.status_code == 200
    fixes_body = fixes_response.json()

    assert {f["id"] for f in fixes_body} == set(expected_fixes)
    for item in fixes_body:
        expected = expected_fixes[item["id"]]
        assert item["issue_id"] == expected["issue_id"]
        assert item["fix_type"] == expected["fix_type"]
        assert item["auto_applicable"] == expected["auto_applicable"]
        assert item["proposed_value"] == expected["proposed_value"]
        assert item["reason"] == expected["reason"]
        assert item["status"] == expected["status"]
