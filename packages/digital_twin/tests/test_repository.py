"""Unit tests for the Digital_Twin repository (task 4.2).

These exercise :class:`digital_twin.repository.DigitalTwinRepository` against an
in-memory SQLite engine (the ORM uses generic column types, so no PostgreSQL or
Docker is required here). They cover the page round-trip preserving
``crawled_at`` (Req 3.2, 3.3), the freshness boundary (Req 3.4, 3.5), the
unknown-page not-found read (Req 3.6), ignored-issue exclusion (Req 4.11),
audit-trail append/read ordering, and tenant stamping/rejection (Req 14.5,
14.6). The universal property variants live in tasks 4.3-4.9.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.exceptions import DigitalTwinError
from core.results import NotFound, Ok, Stale
from core.types import (
    AuditEntry,
    CrawledPage,
    FixStatus,
    FixType,
    IssueCandidate,
    IssueDetail,
    IssueType,
    LinkStatus,
    Severity,
    SuggestedFix,
)

from digital_twin.models import Base
from digital_twin.repository import DigitalTwinRepository

TENANT = "tenant-a"
URL = "https://example.com/page"


@pytest.fixture()
def session_factory():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture()
def repo(session_factory):
    # Threshold of one hour, expressed as seconds to prove seconds are accepted.
    return DigitalTwinRepository(
        session_factory, tenant_id=TENANT, staleness_threshold=3600
    )


def _page(crawled_at: datetime, *, url: str = URL) -> CrawledPage:
    return CrawledPage(
        url=url,
        final_url=url,
        status_code=200,
        title="Home",
        meta_description="A page",
        word_count=42,
        has_schema=True,
        links=[
            LinkStatus(url="https://example.com/ok", status_code=200, reachable=True),
            LinkStatus(url="https://example.com/dead", status_code=404, reachable=False),
        ],
        crawled_at=crawled_at,
    )


# --- Page round-trip (Req 3.2, 3.3) ------------------------------------------


def test_upsert_then_get_page_round_trip_preserves_crawled_at(repo):
    crawled_at = datetime(2024, 1, 1, 12, 30, 45, 123456, tzinfo=timezone.utc)
    repo.upsert_pages(TENANT, [_page(crawled_at)])

    result = repo.get_page(TENANT, URL, now=crawled_at + timedelta(minutes=1))

    assert isinstance(result, Ok)
    page = result.unwrap()
    assert page.url == URL
    assert page.title == "Home"
    assert page.meta_description == "A page"
    assert page.word_count == 42
    assert page.has_schema is True
    assert page.crawled_at == crawled_at
    assert {link.url for link in page.links} == {
        "https://example.com/ok",
        "https://example.com/dead",
    }


def test_upsert_updates_existing_page_in_place(repo):
    first = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    repo.upsert_pages(TENANT, [_page(first)])
    updated = _page(first + timedelta(minutes=5))
    updated = updated.model_copy(update={"title": "Updated", "word_count": 100})
    repo.upsert_pages(TENANT, [updated])

    result = repo.get_page(TENANT, URL, now=first + timedelta(minutes=6))
    assert isinstance(result, Ok)
    page = result.unwrap()
    assert page.title == "Updated"
    assert page.word_count == 100


# --- Freshness boundary (Req 3.4, 3.5) ---------------------------------------


def test_page_exactly_at_threshold_is_fresh(repo):
    crawled_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
    repo.upsert_pages(TENANT, [_page(crawled_at)])
    # age == threshold -> within the threshold -> served (Req 3.4).
    result = repo.get_page(TENANT, URL, now=crawled_at + timedelta(seconds=3600))
    assert isinstance(result, Ok)


def test_page_just_past_threshold_is_stale(repo):
    crawled_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
    repo.upsert_pages(TENANT, [_page(crawled_at)])
    result = repo.get_page(TENANT, URL, now=crawled_at + timedelta(seconds=3601))
    assert isinstance(result, Stale)
    assert result.crawled_at == crawled_at
    assert result.threshold_seconds == 3600


def test_staleness_threshold_accepts_timedelta(session_factory):
    repo = DigitalTwinRepository(
        session_factory, tenant_id=TENANT, staleness_threshold=timedelta(minutes=1)
    )
    crawled_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
    repo.upsert_pages(TENANT, [_page(crawled_at)])
    assert isinstance(repo.get_page(TENANT, URL, crawled_at + timedelta(seconds=59)), Ok)
    assert isinstance(
        repo.get_page(TENANT, URL, crawled_at + timedelta(seconds=61)), Stale
    )


# --- Unknown page (Req 3.6) --------------------------------------------------


def test_unknown_page_returns_not_found(repo):
    result = repo.get_page(TENANT, "https://example.com/missing", now=datetime.now(timezone.utc))
    assert isinstance(result, NotFound)
    assert result.key == "https://example.com/missing"


def test_page_is_scoped_to_tenant(repo):
    crawled_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
    repo.upsert_pages(TENANT, [_page(crawled_at)])
    # Another tenant cannot see tenant-a's page.
    result = repo.get_page("tenant-b", URL, now=crawled_at + timedelta(minutes=1))
    assert isinstance(result, NotFound)


# --- Issues: persist, list, ignore (Req 4.11) --------------------------------


def _candidate(description: str) -> IssueCandidate:
    return IssueCandidate(
        issue_type=IssueType.MISSING_TITLE,
        severity=Severity.HIGH,
        description=description,
        detail=IssueDetail(page_url=URL, element="head"),
    )


def test_persist_and_list_active_issues_excludes_ignored(repo):
    repo.upsert_pages(TENANT, [_page(datetime(2024, 1, 1, tzinfo=timezone.utc))])
    stored = repo.persist_issues(TENANT, [_candidate("a"), _candidate("b")])
    assert len(stored) == 2
    assert all(issue.tenant_id == TENANT for issue in stored)

    active = repo.list_active_issues(TENANT)
    assert {i.description for i in active} == {"a", "b"}

    repo.mark_issue_ignored(TENANT, stored[0].id)
    active_after = repo.list_active_issues(TENANT)
    assert {i.description for i in active_after} == {"b"}


def test_persist_issue_for_unstored_page_is_rejected(repo):
    with pytest.raises(DigitalTwinError):
        repo.persist_issues(TENANT, [_candidate("orphan")])


# --- Fixes -------------------------------------------------------------------


def test_persist_fixes_stamps_tenant_and_returns_records(repo):
    repo.upsert_pages(TENANT, [_page(datetime(2024, 1, 1, tzinfo=timezone.utc))])
    issue = repo.persist_issues(TENANT, [_candidate("x")])[0]
    fix = SuggestedFix(
        id="fix-1",
        tenant_id="",  # to be stamped by the repository
        issue_id=issue.id,
        fix_type=FixType.UPDATE_ALT_TEXT,
        auto_applicable=1,
        proposed_value="alt text",
        reason=None,
        status=FixStatus.PENDING,
    )
    stored = repo.persist_fixes(TENANT, [fix])
    assert len(stored) == 1
    assert stored[0].tenant_id == TENANT
    assert stored[0].id == "fix-1"


# --- Audit trail -------------------------------------------------------------


def test_audit_trail_append_and_read_most_recent_first(repo):
    repo.upsert_pages(TENANT, [_page(datetime(2024, 1, 1, tzinfo=timezone.utc))])
    issue = repo.persist_issues(TENANT, [_candidate("x")])[0]
    repo.persist_fixes(
        TENANT,
        [
            SuggestedFix(
                id="fix-1",
                tenant_id=TENANT,
                issue_id=issue.id,
                fix_type=FixType.UPDATE_ALT_TEXT,
                auto_applicable=1,
                status=FixStatus.PENDING,
            )
        ],
    )
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    for i in range(3):
        repo.append_audit_entry(
            TENANT,
            AuditEntry(
                id=f"a{i}",
                tenant_id=TENANT,
                fix_id="fix-1",
                actor="alice",
                rationale="because",
                transition="pending->approved",
                created_at=base + timedelta(minutes=i),
            ),
        )

    entries = repo.list_audit_entries(TENANT)
    assert [e.id for e in entries] == ["a2", "a1", "a0"]


# --- Tenant stamping / rejection (Req 14.5, 14.6) ----------------------------


def test_upsert_with_no_resolvable_tenant_is_rejected_and_persists_nothing(
    session_factory,
):
    # No configured tenant and an empty call tenant -> rejected before any write.
    repo = DigitalTwinRepository(session_factory, tenant_id=None)
    page = _page(datetime(2024, 1, 1, tzinfo=timezone.utc))
    with pytest.raises(DigitalTwinError):
        repo.upsert_pages("", [page])
    with pytest.raises(DigitalTwinError):
        repo.upsert_pages("   ", [page])

    # Nothing was persisted: a valid-tenant read finds no page.
    ok_repo = DigitalTwinRepository(session_factory, tenant_id=TENANT)
    assert isinstance(
        ok_repo.get_page(TENANT, URL, now=datetime.now(timezone.utc)), NotFound
    )


def test_configured_tenant_is_used_when_call_tenant_is_missing(session_factory):
    repo = DigitalTwinRepository(session_factory, tenant_id=TENANT)
    crawled_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
    # Empty call tenant falls back to the configured tenant.
    repo.upsert_pages("", [_page(crawled_at)])
    result = repo.get_page("", URL, now=crawled_at + timedelta(minutes=1))
    assert isinstance(result, Ok)
