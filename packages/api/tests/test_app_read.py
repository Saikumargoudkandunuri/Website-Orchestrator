"""Unit/integration tests for the API_Surface read endpoints (task 13.2).

These are network-free: the FastAPI :class:`~fastapi.testclient.TestClient`
drives the app and the Digital_Twin is a real
:class:`~digital_twin.repository.DigitalTwinRepository` backed by in-memory
SQLite, seeded directly through the repository. The other subsystems are minimal
fakes that satisfy the composition root but are never invoked by these reads.

Coverage:

* ``GET /issues`` returns the persisted issues (Req 10.2).
* ``GET /fixes`` returns the persisted suggested fixes (Req 10.3).
* ``GET /audit-log`` returns Audit_Trail entries ordered most-recent first
  (Req 10.7).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from check_engine import CheckEngine
from digital_twin.models import Base
from digital_twin.repository import DigitalTwinRepository
from fix_generator import FixGenerator
from governance.service import GovernanceService

from core.types import (
    AuditEntry,
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


# --- Fakes --------------------------------------------------------------------


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


# --- App builder --------------------------------------------------------------


def _build_app():
    """Build an app wired to a real in-memory repo, returning ``(app, repo)``."""
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
                url="https://example.com/",
                final_url="https://example.com/",
                status_code=200,
                crawled_at=now,
            )
        ],
    )


# --- GET /issues (Req 10.2) ---------------------------------------------------


def test_get_issues_returns_persisted_issues() -> None:
    app, repo = _build_app()
    _seed_page(repo)
    stored = repo.persist_issues(
        TENANT,
        [
            IssueCandidate(
                issue_type=IssueType.MISSING_TITLE,
                severity=Severity.HIGH,
                description="Page has no title",
                detail=IssueDetail(page_url="https://example.com/"),
            ),
            IssueCandidate(
                issue_type=IssueType.THIN_CONTENT,
                severity=Severity.MEDIUM,
                description="Page has thin content",
                detail=IssueDetail(page_url="https://example.com/"),
            ),
        ],
    )
    client = TestClient(app)

    response = client.get("/issues")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    assert {i["id"] for i in body} == {i.id for i in stored}
    assert {i["issue_type"] for i in body} == {"missing_title", "thin_content"}


def test_get_issues_empty_when_none_persisted() -> None:
    app, _repo = _build_app()
    client = TestClient(app)

    response = client.get("/issues")

    assert response.status_code == 200
    assert response.json() == []


# --- GET /fixes (Req 10.3) ----------------------------------------------------


def test_get_fixes_returns_all_persisted_fixes_regardless_of_status() -> None:
    app, repo = _build_app()
    fixes = [
        SuggestedFix(
            id="fix-pending",
            tenant_id=TENANT,
            issue_id="issue-1",
            fix_type=FixType.UPDATE_ALT_TEXT,
            auto_applicable=1,
            proposed_value="A red bike",
            status=FixStatus.PENDING,
        ),
        SuggestedFix(
            id="fix-applied",
            tenant_id=TENANT,
            issue_id="issue-2",
            fix_type=FixType.UPDATE_PAGE_CONTENT,
            auto_applicable=0,
            reason="Report only",
            status=FixStatus.APPLIED,
        ),
    ]
    repo.persist_fixes(TENANT, fixes)
    client = TestClient(app)

    response = client.get("/fixes")

    assert response.status_code == 200
    body = response.json()
    # All persisted fixes are returned, not just the pending one (Req 10.3).
    assert {f["id"] for f in body} == {"fix-pending", "fix-applied"}
    assert {f["status"] for f in body} == {"pending", "applied"}


def test_get_fixes_empty_when_none_persisted() -> None:
    app, _repo = _build_app()
    client = TestClient(app)

    response = client.get("/fixes")

    assert response.status_code == 200
    assert response.json() == []


# --- GET /audit-log (Req 10.7) ------------------------------------------------


def test_get_audit_log_returns_entries_most_recent_first() -> None:
    app, repo = _build_app()
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    # Append out of chronological order to prove the endpoint orders by time.
    repo.append_audit_entry(
        TENANT,
        AuditEntry(
            id="audit-old",
            tenant_id=TENANT,
            fix_id="fix-1",
            actor="alice",
            rationale="approve first",
            transition="pending->approved",
            created_at=base,
        ),
    )
    repo.append_audit_entry(
        TENANT,
        AuditEntry(
            id="audit-new",
            tenant_id=TENANT,
            fix_id="fix-1",
            actor="bob",
            rationale="rollback later",
            transition="applied->rolled_back",
            created_at=base + timedelta(hours=2),
        ),
    )
    client = TestClient(app)

    response = client.get("/audit-log")

    assert response.status_code == 200
    body = response.json()
    assert [e["id"] for e in body] == ["audit-new", "audit-old"]


def test_get_audit_log_empty_when_none_persisted() -> None:
    app, _repo = _build_app()
    client = TestClient(app)

    response = client.get("/audit-log")

    assert response.status_code == 200
    assert response.json() == []
