"""Property 12 — Unknown page reads return not-found.

Feature: website-orchestrator-milestone-0, Property 12: Unknown page reads
return not-found

Validates: Requirements 3.6

Requirement 3.6: WHEN a page is read that is not stored in the Digital_Twin,
THE Digital_Twin SHALL report the miss as a :class:`~core.results.NotFound`
read sentinel, returning no page data.

This property drives
:meth:`digital_twin.repository.DigitalTwinRepository.get_page` for URLs that are
*not* stored for the queried tenant. Regardless of the read ``now`` and
regardless of whether the store is empty, holds unrelated pages, or holds the
same URL under a *different* tenant, the read must return a
:class:`~core.results.NotFound` (never an :class:`~core.results.Ok` and never a
:class:`~core.results.Stale`) and must therefore carry no reconstructed page.

Three scenarios are covered by dedicated property tests:

* an empty database queried for an arbitrary URL,
* a database populated with some pages but queried for a *different* (absent)
  URL (``assume`` guarantees the queried URL differs from every stored URL),
* a URL stored for tenant A that is queried under tenant B (cross-tenant miss).

Each example uses a fresh in-memory SQLite database (the ORM uses generic column
types, so no PostgreSQL or Docker is required) so examples are independent.
The read ``now`` is generated freely to show freshness never turns an absent
page into a hit.
"""

from __future__ import annotations

from datetime import datetime, timezone

from hypothesis import assume, given, settings
from hypothesis import strategies as st
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.results import NotFound
from core.types import CrawledPage, LinkStatus

from digital_twin.models import Base
from digital_twin.repository import DigitalTwinRepository

TENANT_A = "tenant-a"
TENANT_B = "tenant-b"

# --- Strategies ---------------------------------------------------------------

# Non-empty, non-blank text for URLs / tenant identifiers.
# Excludes NUL (0x00) and surrogates because PostgreSQL TEXT fields reject both.
_non_blank = st.text(
    alphabet=st.characters(blacklist_characters="\x00", blacklist_categories=("Cs",)),
    min_size=1, max_size=60,
).filter(lambda s: s.strip() != "")

# Read timestamps generated freely (UTC-aware) so freshness cannot turn a miss
# into a hit — a NotFound must not depend on how "recent" the read is.
_utc_datetimes = st.datetimes(
    min_value=datetime(2000, 1, 1),
    max_value=datetime(2100, 1, 1),
    timezones=st.just(timezone.utc),
)

_links = st.builds(
    LinkStatus,
    url=_non_blank,
    status_code=st.one_of(st.none(), st.integers(min_value=100, max_value=599)),
    reachable=st.booleans(),
)


@st.composite
def _crawled_pages(draw: st.DrawFn) -> CrawledPage:
    """A CrawledPage with a UTC-aware ``crawled_at`` and varied persisted fields."""
    return CrawledPage(
        url=draw(_non_blank),
        final_url=draw(_non_blank),
        status_code=draw(st.integers(min_value=100, max_value=599)),
        title=draw(st.one_of(st.none(), _non_blank)),
        meta_description=draw(st.one_of(st.none(), _non_blank)),
        word_count=draw(st.integers(min_value=0, max_value=1_000_000)),
        has_schema=draw(st.booleans()),
        links=draw(st.lists(_links, max_size=6)),
        crawled_at=draw(_utc_datetimes),
    )


def _fresh_repo(tenant_id: str) -> DigitalTwinRepository:
    """A repository over a fresh in-memory DB scoped to ``tenant_id``."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    return DigitalTwinRepository(factory, tenant_id=tenant_id)


def _assert_not_found(result, url: str) -> None:
    """Assert the read is a NotFound naming ``url`` and carries no page data."""
    assert isinstance(result, NotFound)
    # No page data: a NotFound is neither Ok nor Stale and exposes no value.
    assert result.is_ok is False
    assert result.is_err is False
    assert not hasattr(result, "value")
    # The miss records the requested key (Req 3.6).
    assert result.key == url


# --- Property 12 --------------------------------------------------------------


@settings(max_examples=100)
@given(url=_non_blank, now=_utc_datetimes)
def test_property_12_empty_db_read_is_not_found(url: str, now: datetime) -> None:
    """Reading any URL from an empty Digital_Twin returns NotFound (Req 3.6).

    Feature: website-orchestrator-milestone-0, Property 12: Unknown page reads
    return not-found

    Validates: Requirements 3.6
    """
    repo = _fresh_repo(TENANT_A)

    result = repo.get_page(TENANT_A, url, now=now)

    _assert_not_found(result, url)


@settings(max_examples=100)
@given(
    stored=st.lists(_crawled_pages(), min_size=1, max_size=6),
    missing_url=_non_blank,
    now=_utc_datetimes,
)
def test_property_12_absent_url_among_stored_pages_is_not_found(
    stored: list[CrawledPage], missing_url: str, now: datetime
) -> None:
    """Reading a URL that differs from every stored page returns NotFound.

    The store holds some pages, but the queried URL is guaranteed distinct from
    all of them, so the read must still miss (Req 3.6).

    Feature: website-orchestrator-milestone-0, Property 12: Unknown page reads
    return not-found

    Validates: Requirements 3.6
    """
    stored_urls = {page.url for page in stored}
    assume(missing_url not in stored_urls)

    repo = _fresh_repo(TENANT_A)
    repo.upsert_pages(TENANT_A, stored)

    result = repo.get_page(TENANT_A, missing_url, now=now)

    _assert_not_found(result, missing_url)


@settings(max_examples=100)
@given(page=_crawled_pages(), now=_utc_datetimes)
def test_property_12_cross_tenant_read_is_not_found(
    page: CrawledPage, now: datetime
) -> None:
    """A URL stored for tenant A is NotFound when read under tenant B (Req 3.6).

    Feature: website-orchestrator-milestone-0, Property 12: Unknown page reads
    return not-found

    Validates: Requirements 3.6
    """
    # A single shared in-memory DB, but two repositories scoped to the two
    # tenants so tenant B queries the same store that holds tenant A's page.
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    repo_a = DigitalTwinRepository(factory, tenant_id=TENANT_A)
    repo_b = DigitalTwinRepository(factory, tenant_id=TENANT_B)

    repo_a.upsert_pages(TENANT_A, [page])

    result = repo_b.get_page(TENANT_B, page.url, now=now)

    _assert_not_found(result, page.url)
