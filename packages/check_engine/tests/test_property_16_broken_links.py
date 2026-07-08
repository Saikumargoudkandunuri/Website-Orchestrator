"""Property 16 — Broken-links detection matches error statuses.

Feature: website-orchestrator-milestone-0, Property 16: Broken-links detection
matches error statuses

Validates: Requirements 4.5

Requirement 4.5: WHEN a link has a client or server error status, THE Check_Engine
SHALL emit a broken-links IssueCandidate.

This property drives :meth:`check_engine.CheckEngine.check_broken_links` with a
:class:`~core.types.CrawledPage` carrying an arbitrary mix of
:class:`~core.types.LinkStatus` records. A link is *broken* exactly when its
``status_code`` is a client/server error status, i.e. an integer in the closed
range ``[400, 599]``; links with a 2xx/3xx status or a ``None`` status (unreachable)
are never broken.

For every generated page the test computes the expected broken set *independently*
of the implementation (a straightforward ``400 <= code <= 599`` filter) and asserts:

* exactly one candidate is emitted per broken link (count matches), and
* the set of flagged link URLs equals the independently-computed expected set, and
* every emitted candidate is a well-formed ``BROKEN_LINKS`` IssueCandidate — valid
  severity, non-empty description, and ``detail.page_url == page.url``.

Statuses are drawn from a pool of boundary values (None, 200, 201, 301, 399, 400,
404, 500, 599) mixed with random integers spanning 100–599, so both sides of every
threshold (399/400 and 599/600-and-beyond via the wider integer band) are exercised.
"""

from __future__ import annotations

from datetime import datetime, timezone

from hypothesis import given, settings
from hypothesis import strategies as st

from core.types import (
    CrawledPage,
    IssueType,
    LinkStatus,
    Severity,
)

from check_engine import CheckEngine

_VALID_SEVERITIES = {
    Severity.CRITICAL,
    Severity.HIGH,
    Severity.MEDIUM,
    Severity.LOW,
}


def _is_error_status(status_code: int | None) -> bool:
    """Independent reference: True iff ``status_code`` is a 4xx/5xx error."""

    return status_code is not None and 400 <= status_code <= 599


# --- Strategies ---------------------------------------------------------------

# Boundary / representative statuses called out by the property, mixed with a
# wide integer band so values just inside and just outside [400, 599] appear.
_status_codes = st.one_of(
    st.sampled_from([None, 200, 201, 301, 399, 400, 404, 500, 599]),
    st.integers(min_value=100, max_value=599),
    # A few values above 599 so the upper bound (<= 599) is genuinely tested.
    st.integers(min_value=600, max_value=699),
)

# A list of statuses; index-based URLs are attached later to guarantee uniqueness.
_status_lists = st.lists(_status_codes, min_size=0, max_size=25)


def _make_links(status_codes: list[int | None]) -> list[LinkStatus]:
    """Build LinkStatus records with unique, index-derived URLs."""

    return [
        LinkStatus(
            url=f"https://example.com/link/{index}",
            status_code=code,
            reachable=code is not None,
        )
        for index, code in enumerate(status_codes)
    ]


@settings(max_examples=200)
@given(status_codes=_status_lists)
def test_property_16_broken_links_detection_matches_error_statuses(
    status_codes: list[int | None],
) -> None:
    """For any page, ``check_broken_links`` emits exactly one well-formed
    BROKEN_LINKS candidate per link whose status is in [400, 599], and none for
    2xx/3xx/None links.

    Feature: website-orchestrator-milestone-0, Property 16: Broken-links detection
    matches error statuses

    Validates: Requirements 4.5
    """
    links = _make_links(status_codes)
    page_url = "https://example.com/page-under-test"
    page = CrawledPage(
        url=page_url,
        final_url=page_url,
        status_code=200,
        links=links,
        crawled_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )

    # Independently computed expectation.
    expected_broken = [link for link in links if _is_error_status(link.status_code)]
    expected_count = len(expected_broken)
    expected_urls = {link.url for link in expected_broken}

    candidates = CheckEngine().check_broken_links(page)

    # Count matches: exactly one candidate per broken link.
    assert len(candidates) == expected_count

    # The set of flagged link URLs matches the expected set. Each candidate's
    # detail.element is "<url> (status <code>)"; recover the URL prefix.
    flagged_urls = {
        candidate.detail.element.split(" (status")[0]
        for candidate in candidates
        if candidate.detail.element is not None
    }
    assert flagged_urls == expected_urls

    # No non-broken link is ever flagged (2xx/3xx/None must be absent).
    for link in links:
        if not _is_error_status(link.status_code):
            assert link.url not in flagged_urls

    # Every emitted candidate is a well-formed BROKEN_LINKS issue.
    for candidate in candidates:
        assert candidate.issue_type is IssueType.BROKEN_LINKS
        assert candidate.severity in _VALID_SEVERITIES
        assert candidate.description.strip() != ""
        assert candidate.detail.page_url == page_url
