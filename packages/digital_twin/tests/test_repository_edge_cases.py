"""Focused edge-case unit tests for the Digital_Twin repository (task 4.9).

These example-based tests complement the property test in task 4.4
(``test_property_11_freshness.py``) and the broader unit tests in
``test_repository.py`` by pinning down two easily-overlooked corners of the
persistence contract:

* the exact staleness boundary (age == threshold is fresh -> Req 3.4; the
  smallest step beyond the threshold is stale -> Req 3.5), exercised with both
  a ``timedelta`` threshold and a seconds threshold; plus the degenerate
  freshness cases (a very large threshold is always fresh, zero-ish age is
  fresh); and
* empty write batches (``upsert_pages``/``persist_issues``/``persist_fixes``
  with ``[]``) which must be harmless no-ops that persist nothing and never
  raise, leaving subsequent reads at not-found.

They run against an in-memory SQLite engine (the ORM uses generic column types)
so no PostgreSQL or Docker is required.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.results import NotFound, Ok, Stale
from core.types import CrawledPage, LinkStatus

from digital_twin.models import Base
from digital_twin.repository import DigitalTwinRepository

TENANT = "tenant-a"
URL = "https://example.com/page"


@pytest.fixture()
def session_factory():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


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
        ],
        crawled_at=crawled_at,
    )


# --- Staleness boundary, seconds threshold (Req 3.4, 3.5) --------------------


def test_seconds_threshold_age_exactly_at_threshold_is_fresh(session_factory):
    """age == threshold is *within* the threshold, so the page is served (Req 3.4)."""
    repo = DigitalTwinRepository(
        session_factory, tenant_id=TENANT, staleness_threshold=3600
    )
    crawled_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
    repo.upsert_pages(TENANT, [_page(crawled_at)])

    result = repo.get_page(TENANT, URL, now=crawled_at + timedelta(seconds=3600))

    assert isinstance(result, Ok)


def test_seconds_threshold_one_microsecond_past_threshold_is_stale(session_factory):
    """The smallest representable step beyond the threshold is stale (Req 3.5)."""
    repo = DigitalTwinRepository(
        session_factory, tenant_id=TENANT, staleness_threshold=3600
    )
    crawled_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
    repo.upsert_pages(TENANT, [_page(crawled_at)])

    now = crawled_at + timedelta(seconds=3600, microseconds=1)
    result = repo.get_page(TENANT, URL, now=now)

    assert isinstance(result, Stale)
    assert result.crawled_at == crawled_at
    assert result.threshold_seconds == 3600.0
    assert result.age_seconds == pytest.approx(3600.000001)


# --- Staleness boundary, timedelta threshold (Req 3.4, 3.5) ------------------


def test_timedelta_threshold_age_exactly_at_threshold_is_fresh(session_factory):
    repo = DigitalTwinRepository(
        session_factory,
        tenant_id=TENANT,
        staleness_threshold=timedelta(minutes=30),
    )
    crawled_at = datetime(2024, 6, 1, 8, 0, 0, tzinfo=timezone.utc)
    repo.upsert_pages(TENANT, [_page(crawled_at)])

    result = repo.get_page(TENANT, URL, now=crawled_at + timedelta(minutes=30))

    assert isinstance(result, Ok)


def test_timedelta_threshold_one_microsecond_past_threshold_is_stale(session_factory):
    repo = DigitalTwinRepository(
        session_factory,
        tenant_id=TENANT,
        staleness_threshold=timedelta(minutes=30),
    )
    crawled_at = datetime(2024, 6, 1, 8, 0, 0, tzinfo=timezone.utc)
    repo.upsert_pages(TENANT, [_page(crawled_at)])

    now = crawled_at + timedelta(minutes=30, microseconds=1)
    result = repo.get_page(TENANT, URL, now=now)

    assert isinstance(result, Stale)
    assert result.threshold_seconds == 1800.0


# --- Degenerate freshness cases (Req 3.4) ------------------------------------


def test_zero_age_is_fresh(session_factory):
    """A page read at its own crawl instant (age == 0) is fresh (Req 3.4)."""
    repo = DigitalTwinRepository(
        session_factory, tenant_id=TENANT, staleness_threshold=3600
    )
    crawled_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
    repo.upsert_pages(TENANT, [_page(crawled_at)])

    assert isinstance(repo.get_page(TENANT, URL, now=crawled_at), Ok)


def test_very_large_threshold_is_always_fresh(session_factory):
    """A very large threshold keeps even an old page fresh (Req 3.4)."""
    repo = DigitalTwinRepository(
        session_factory,
        tenant_id=TENANT,
        staleness_threshold=timedelta(days=3650),
    )
    crawled_at = datetime(2000, 1, 1, tzinfo=timezone.utc)
    repo.upsert_pages(TENANT, [_page(crawled_at)])

    # Ten years after the crawl, still within a ~ten-year threshold.
    now = crawled_at + timedelta(days=3649)
    assert isinstance(repo.get_page(TENANT, URL, now=now), Ok)


# --- Empty write batches are harmless no-ops ---------------------------------


def test_empty_upsert_pages_persists_nothing_and_reads_not_found(session_factory):
    repo = DigitalTwinRepository(
        session_factory, tenant_id=TENANT, staleness_threshold=3600
    )

    # A no-op that neither raises nor persists anything.
    repo.upsert_pages(TENANT, [])

    result = repo.get_page(TENANT, URL, now=datetime.now(timezone.utc))
    assert isinstance(result, NotFound)
    assert result.key == URL


def test_empty_persist_issues_returns_empty_list(session_factory):
    repo = DigitalTwinRepository(
        session_factory, tenant_id=TENANT, staleness_threshold=3600
    )

    assert repo.persist_issues(TENANT, []) == []
    # Nothing was persisted.
    assert repo.list_active_issues(TENANT) == []


def test_empty_persist_fixes_returns_empty_list(session_factory):
    repo = DigitalTwinRepository(
        session_factory, tenant_id=TENANT, staleness_threshold=3600
    )

    assert repo.persist_fixes(TENANT, []) == []
    # Nothing was persisted.
    assert repo.list_pending_fixes(TENANT) == []


def test_empty_batches_do_not_interfere_with_subsequent_writes(session_factory):
    """An empty batch is inert: a real write immediately after still lands."""
    repo = DigitalTwinRepository(
        session_factory, tenant_id=TENANT, staleness_threshold=3600
    )
    repo.upsert_pages(TENANT, [])
    repo.persist_issues(TENANT, [])
    repo.persist_fixes(TENANT, [])

    crawled_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
    repo.upsert_pages(TENANT, [_page(crawled_at)])

    result = repo.get_page(TENANT, URL, now=crawled_at + timedelta(minutes=1))
    assert isinstance(result, Ok)
