"""Property 10 — Page persistence round-trip preserves crawled_at.

Feature: website-orchestrator-milestone-0, Property 10: Page persistence
round-trip preserves crawled_at

Validates: Requirements 3.2, 3.3

Requirement 3.2: THE Digital_Twin SHALL persist each crawled page with a UTC
``crawled_at`` timestamp.

Requirement 3.3: WHEN a stored page is read back within the Staleness_Threshold,
THE Digital_Twin SHALL reconstruct the CrawledPage preserving the persisted
fields exactly — critically the ``crawled_at`` timestamp.

This property drives :meth:`digital_twin.repository.DigitalTwinRepository.upsert_pages`
followed by :meth:`~digital_twin.repository.DigitalTwinRepository.get_page` for any
generated :class:`~core.types.CrawledPage`. The read is taken with ``now`` set to
the page's own ``crawled_at`` so the age is zero and the read always returns an
:class:`~core.results.Ok` (well inside the Staleness_Threshold).

Each example uses a fresh in-memory SQLite database (the ORM uses generic column
types, so no PostgreSQL or Docker is required) so examples are independent.

The M0 relational schema does not persist a page's raw HTML, image references, or
per-page redirect chain, so those are excluded from the round-trip assertions.
The persisted fields — ``url``, ``final_url``, ``status_code``, ``title``,
``meta_description``, ``word_count``, ``has_schema``, ``links``, and crucially
``crawled_at`` — are asserted to round-trip exactly.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from hypothesis import given, settings
from hypothesis import strategies as st
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.results import Ok
from core.types import CrawledPage, LinkStatus

from digital_twin.models import Base
from digital_twin.repository import DigitalTwinRepository

TENANT = "tenant-a"

# --- Strategies ---------------------------------------------------------------

# Non-empty, non-blank text for identifiers/URLs so upsert matching on url works.
# Excludes NUL (0x00) and surrogates because PostgreSQL TEXT fields reject both.
_non_blank = st.text(
    alphabet=st.characters(blacklist_characters="\x00", blacklist_categories=("Cs",)),
    min_size=1, max_size=60,
).filter(lambda s: s.strip() != "")

# UTC-aware timestamps. The repository normalizes to UTC and SQLite drops the
# tzinfo, so generating UTC-aware values keeps the exact-equality comparison
# meaningful (naive-UTC read back == aware-UTC stored after _to_utc normalization).
_utc_datetimes = st.datetimes(
    min_value=datetime(2000, 1, 1),
    max_value=datetime(2100, 1, 1),
    timezones=st.just(timezone.utc),
)

# A single link's observed status. status_code is None when unreachable.
_links = st.builds(
    LinkStatus,
    url=_non_blank,
    status_code=st.one_of(st.none(), st.integers(min_value=100, max_value=599)),
    reachable=st.booleans(),
)


@st.composite
def _crawled_pages(draw: st.DrawFn) -> CrawledPage:
    """A CrawledPage with a UTC-aware ``crawled_at`` and varied persisted fields."""
    url = draw(_non_blank)
    return CrawledPage(
        url=url,
        final_url=draw(_non_blank),
        status_code=draw(st.integers(min_value=100, max_value=599)),
        title=draw(st.one_of(st.none(), _non_blank)),
        meta_description=draw(st.one_of(st.none(), _non_blank)),
        word_count=draw(st.integers(min_value=0, max_value=1_000_000)),
        has_schema=draw(st.booleans()),
        links=draw(st.lists(_links, max_size=6)),
        crawled_at=draw(_utc_datetimes),
    )


def _fresh_repo() -> DigitalTwinRepository:
    """A repository over a fresh in-memory DB with a wide Staleness_Threshold."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    # A very large threshold guarantees the read is always Ok when now == crawled_at.
    return DigitalTwinRepository(
        factory, tenant_id=TENANT, staleness_threshold=timedelta(days=365_000)
    )


@settings(max_examples=100)
@given(page=_crawled_pages())
def test_property_10_page_round_trip_preserves_crawled_at(page: CrawledPage) -> None:
    """Upserting any CrawledPage and reading it back within the threshold returns
    an Ok whose reconstructed page preserves the persisted fields exactly,
    including the UTC ``crawled_at`` timestamp.

    Feature: website-orchestrator-milestone-0, Property 10: Page persistence
    round-trip preserves crawled_at

    Validates: Requirements 3.2, 3.3
    """
    repo = _fresh_repo()

    repo.upsert_pages(TENANT, [page])

    # Read with now == crawled_at so age is zero and the result is always Ok.
    result = repo.get_page(TENANT, page.url, now=page.crawled_at)

    assert isinstance(result, Ok)
    stored = result.unwrap()

    # Req 3.2, 3.3 — crawled_at is preserved exactly as a UTC-aware instant.
    assert stored.crawled_at == page.crawled_at
    assert stored.crawled_at.tzinfo is not None
    assert stored.crawled_at.utcoffset() == timedelta(0)

    # The other persisted fields round-trip exactly (Req 3.3).
    assert stored.url == page.url
    assert stored.final_url == page.final_url
    assert stored.status_code == page.status_code
    assert stored.title == page.title
    assert stored.meta_description == page.meta_description
    assert stored.word_count == page.word_count
    assert stored.has_schema == page.has_schema

    # Links round-trip as an unordered multiset of (url, status_code, reachable).
    # A missing status_code (None) sorts as -1 so int/None stay comparable.
    def _key(link: LinkStatus) -> tuple[str, int, bool]:
        return (link.url, link.status_code if link.status_code is not None else -1, link.reachable)

    assert sorted(map(_key, stored.links)) == sorted(map(_key, page.links))
