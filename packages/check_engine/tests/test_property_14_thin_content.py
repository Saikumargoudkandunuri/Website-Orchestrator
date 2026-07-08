"""Property 14 — Thin-content detection matches the word-count threshold.

Feature: website-orchestrator-milestone-0, Property 14: Thin-content detection matches the word-count threshold

Validates: Requirements 4.3

Requirement 4.3: THE Check_Engine SHALL flag a page as thin content when its
word count is below the configured minimum (``THIN_CONTENT_MIN_WORDS``, default
300 words).

This property drives :meth:`~check_engine.CheckEngine.check_thin_content` with a
Hypothesis-generated ``word_count`` spanning the region below, at, and above the
configured threshold and asserts the exact biconditional the requirement states:

* ``word_count < THIN_CONTENT_MIN_WORDS``  → emits a THIN_CONTENT candidate.
* ``word_count >= THIN_CONTENT_MIN_WORDS`` → returns ``None`` (including the
  exact boundary ``word_count == THIN_CONTENT_MIN_WORDS``).

When a candidate is emitted it must be well-formed (Req 4.8): the issue type is
``THIN_CONTENT``, the severity is one of ``critical | high | medium | low``, the
description is a non-empty human-readable string, and the detail locates the
affected page URL.
"""

from __future__ import annotations

from datetime import datetime, timezone

from hypothesis import given, settings
from hypothesis import strategies as st

from check_engine import CheckEngine
from core.constants import THIN_CONTENT_MIN_WORDS
from core.types import CrawledPage, IssueType, Severity

# --- Strategies ---------------------------------------------------------------

_VALID_SEVERITIES = {
    Severity.CRITICAL,
    Severity.HIGH,
    Severity.MEDIUM,
    Severity.LOW,
}

# Word counts spanning the thin-content threshold: a band well below, the region
# straddling the boundary (which always includes the exact boundary value), and
# a band well above. Non-negative, since a page's word count is never negative.
_word_counts = st.one_of(
    st.integers(min_value=0, max_value=max(THIN_CONTENT_MIN_WORDS - 1, 0)),
    st.integers(
        min_value=max(THIN_CONTENT_MIN_WORDS - 5, 0),
        max_value=THIN_CONTENT_MIN_WORDS + 5,
    ),
    st.integers(
        min_value=THIN_CONTENT_MIN_WORDS,
        max_value=THIN_CONTENT_MIN_WORDS + 1000,
    ),
)

_urls = st.text(min_size=1, max_size=40).filter(lambda s: s.strip() != "")


@st.composite
def _pages(draw: st.DrawFn) -> CrawledPage:
    """A CrawledPage whose ``word_count`` spans the thin-content threshold.

    Every other field is held healthy so ``check_thin_content`` is judged solely
    on ``word_count``.
    """
    url = draw(_urls)
    return CrawledPage(
        url=url,
        final_url=url,
        status_code=200,
        title="A perfectly good title",
        meta_description="A perfectly good meta description.",
        word_count=draw(_word_counts),
        has_schema=True,
        crawled_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )


# --- Property -----------------------------------------------------------------


@settings(max_examples=200)
@given(page=_pages())
def test_property_14_thin_content_matches_threshold(page: CrawledPage) -> None:
    """For any page word count, ``check_thin_content`` emits a THIN_CONTENT
    candidate iff ``word_count < THIN_CONTENT_MIN_WORDS`` and returns ``None``
    iff ``word_count >= THIN_CONTENT_MIN_WORDS`` (including the exact boundary).

    Feature: website-orchestrator-milestone-0, Property 14: Thin-content detection matches the word-count threshold

    Validates: Requirements 4.3
    """
    result = CheckEngine().check_thin_content(page)

    if page.word_count < THIN_CONTENT_MIN_WORDS:
        # Below threshold: a well-formed THIN_CONTENT candidate is emitted.
        assert result is not None
        assert result.issue_type is IssueType.THIN_CONTENT
        assert result.severity in _VALID_SEVERITIES
        assert result.description.strip() != ""
        assert result.detail.page_url == page.url
    else:
        # At or above threshold (incl. word_count == threshold): no issue.
        assert result is None
