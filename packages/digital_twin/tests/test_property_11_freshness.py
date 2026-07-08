"""Property 11 — Freshness decision matches the staleness threshold.

Feature: website-orchestrator-milestone-0, Property 11: Freshness decision
matches the staleness threshold

Validates: Requirements 3.4, 3.5

Requirement 3.4: WHILE the age of a requested page (elapsed time since its
``crawled_at``) is within the configured Staleness_Threshold, THE Digital_Twin
SHALL serve the page data for action (an :class:`~core.results.Ok`).

Requirement 3.5: IF the age of a requested page exceeds the configured
Staleness_Threshold, THEN THE Digital_Twin SHALL indicate the page is stale (a
:class:`~core.results.Stale`) and require a re-crawl before the data is used.

The universal property under test: for any stored page with a UTC-aware
``crawled_at``, any positive Staleness_Threshold, and any read time ``now``,
:meth:`digital_twin.repository.DigitalTwinRepository.get_page` returns an
:class:`~core.results.Ok` exactly when the age ``now - crawled_at`` is at or
below the threshold (the boundary ``age == threshold`` is *fresh*), and a
:class:`~core.results.Stale` once the age exceeds the threshold.

The age offset is generated to straddle the boundary — strictly below, exactly
at, and strictly above the threshold — so the decision boundary itself is
exercised, including the exact ``age == threshold`` fresh case.

Each example uses a fresh in-memory SQLite database (the ORM uses generic column
types, so no PostgreSQL or Docker is required) so examples are independent.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from hypothesis import given, settings
from hypothesis import strategies as st
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.results import Ok, Stale
from core.types import CrawledPage

from digital_twin.models import Base
from digital_twin.repository import DigitalTwinRepository

TENANT = "tenant-a"
URL = "https://example.com/freshness"


def _fresh_repo(threshold_seconds: float) -> DigitalTwinRepository:
    """A repository over a fresh in-memory DB with the given Staleness_Threshold."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    return DigitalTwinRepository(
        factory, tenant_id=TENANT, staleness_threshold=threshold_seconds
    )


def _page(crawled_at: datetime) -> CrawledPage:
    """A minimal CrawledPage whose freshness turns solely on ``crawled_at``."""
    return CrawledPage(
        url=URL,
        final_url=URL,
        status_code=200,
        title="Home",
        meta_description=None,
        word_count=1,
        has_schema=False,
        links=[],
        crawled_at=crawled_at,
    )


# --- Strategies ---------------------------------------------------------------

# UTC-aware crawl timestamps. Bounded well inside datetime's range so that
# adding the generated age never overflows.
_crawled_at = st.datetimes(
    min_value=datetime(2000, 1, 1),
    max_value=datetime(2090, 1, 1),
    timezones=st.just(timezone.utc),
)

# A positive Staleness_Threshold in seconds (fractional thresholds allowed).
_threshold_seconds = st.floats(
    min_value=1.0, max_value=1_000_000.0, allow_nan=False, allow_infinity=False
)


@st.composite
def _cases(draw: st.DrawFn) -> tuple[datetime, float, float]:
    """Draw ``(crawled_at, threshold_seconds, age_seconds)`` straddling the boundary.

    ``age_seconds`` is drawn to land strictly below, exactly at, or strictly
    above the threshold — plus a broad uniform sample — so both freshness
    outcomes and the exact ``age == threshold`` boundary are covered.
    """
    crawled_at = draw(_crawled_at)
    threshold = draw(_threshold_seconds)
    # A small offset used to sit just inside / just outside the boundary.
    offset = draw(st.floats(min_value=0.001, max_value=threshold, allow_nan=False))
    age = draw(
        st.one_of(
            st.just(threshold),  # exact boundary -> fresh (Req 3.4)
            st.just(max(0.0, threshold - offset)),  # strictly below -> fresh
            st.just(threshold + offset),  # strictly above -> stale (Req 3.5)
            st.floats(  # broad sample across both sides of the boundary
                min_value=0.0,
                max_value=threshold * 2.0,
                allow_nan=False,
                allow_infinity=False,
            ),
        )
    )
    return crawled_at, threshold, age


@settings(max_examples=200)
@given(case=_cases())
def test_property_11_freshness_decision_matches_threshold(
    case: tuple[datetime, float, float],
) -> None:
    """get_page returns Ok iff age <= threshold, else Stale.

    Feature: website-orchestrator-milestone-0, Property 11: Freshness decision
    matches the staleness threshold

    Validates: Requirements 3.4, 3.5
    """
    crawled_at, threshold_seconds, age_seconds = case

    repo = _fresh_repo(threshold_seconds)
    repo.upsert_pages(TENANT, [_page(crawled_at)])

    now = crawled_at + timedelta(seconds=age_seconds)
    result = repo.get_page(TENANT, URL, now=now)

    # Derive the expected decision from the same timedelta arithmetic the
    # repository uses, so microsecond rounding cannot desynchronise the oracle.
    age_delta = timedelta(seconds=age_seconds)
    within_threshold = age_delta <= repo.staleness_threshold

    if within_threshold:
        # Req 3.4 — within the threshold (including the exact boundary) is served.
        assert isinstance(result, Ok)
        assert result.unwrap().crawled_at == crawled_at
    else:
        # Req 3.5 — beyond the threshold is reported stale, no page data served.
        assert isinstance(result, Stale)
        assert result.key == URL
        assert result.crawled_at == crawled_at
        assert result.threshold_seconds == repo.staleness_threshold.total_seconds()


def test_property_11_exact_boundary_is_fresh() -> None:
    """Deterministic witness of the boundary: age == threshold serves the page.

    Feature: website-orchestrator-milestone-0, Property 11: Freshness decision
    matches the staleness threshold

    Validates: Requirements 3.4
    """
    crawled_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
    repo = _fresh_repo(3600)
    repo.upsert_pages(TENANT, [_page(crawled_at)])

    result = repo.get_page(TENANT, URL, now=crawled_at + timedelta(seconds=3600))
    assert isinstance(result, Ok)
