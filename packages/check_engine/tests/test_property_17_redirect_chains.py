"""Property 17 — Redirect-chain detection matches the hop threshold.

Feature: website-orchestrator-milestone-0, Property 17: Redirect-chain detection matches the hop threshold

Validates: Requirements 4.6

Requirement 4.6: THE Check_Engine SHALL flag a page as having a redirect chain
when the number of recorded hops meets or exceeds the configured threshold
(``REDIRECT_CHAIN_THRESHOLD``, default 3 hops).

This property drives :meth:`~check_engine.CheckEngine.check_redirect_chains`
with a Hypothesis-generated hop count spanning the region below, at, and above
the configured threshold and asserts the exact biconditional the requirement
states:

* ``hop_count >= REDIRECT_CHAIN_THRESHOLD`` → emits a REDIRECT_CHAINS candidate
  (including the exact boundary ``hop_count == REDIRECT_CHAIN_THRESHOLD``).
* ``hop_count < REDIRECT_CHAIN_THRESHOLD``  → returns ``None``.

When a candidate is emitted it must be well-formed (Req 4.8): the issue type is
``REDIRECT_CHAINS``, the severity is one of ``critical | high | medium | low``,
the description is a non-empty human-readable string, and the detail locates the
affected page URL.
"""

from __future__ import annotations

from datetime import datetime, timezone

from hypothesis import given, settings
from hypothesis import strategies as st

from check_engine import CheckEngine
from core.constants import REDIRECT_CHAIN_THRESHOLD
from core.types import CrawledPage, IssueType, RedirectChain, Severity

# --- Strategies ---------------------------------------------------------------

_VALID_SEVERITIES = {
    Severity.CRITICAL,
    Severity.HIGH,
    Severity.MEDIUM,
    Severity.LOW,
}

# Redirect hop counts spanning the threshold: a band below, the region
# straddling the boundary (which always includes the exact boundary value), and
# a band above. Non-negative, since a chain never has a negative hop count.
_hop_counts = st.one_of(
    st.integers(min_value=0, max_value=max(REDIRECT_CHAIN_THRESHOLD - 1, 0)),
    st.integers(
        min_value=max(REDIRECT_CHAIN_THRESHOLD - 3, 0),
        max_value=REDIRECT_CHAIN_THRESHOLD + 3,
    ),
    st.integers(
        min_value=REDIRECT_CHAIN_THRESHOLD,
        max_value=REDIRECT_CHAIN_THRESHOLD + 50,
    ),
)

_urls = st.text(min_size=1, max_size=40).filter(lambda s: s.strip() != "")


@st.composite
def _pages(draw: st.DrawFn) -> CrawledPage:
    """A CrawledPage whose redirect chain has a hop count spanning the
    threshold.

    Every other field is held healthy so ``check_redirect_chains`` is judged
    solely on the number of redirect hops.
    """
    url = draw(_urls)
    hop_count = draw(_hop_counts)
    hops = [f"https://example.com/hop/{i}" for i in range(hop_count)]
    return CrawledPage(
        url=url,
        final_url=url,
        status_code=200,
        title="A perfectly good title",
        meta_description="A perfectly good meta description.",
        word_count=1000,
        has_schema=True,
        redirect_chain=RedirectChain(hops=hops, truncated=draw(st.booleans())),
        crawled_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )


# --- Property -----------------------------------------------------------------


@settings(max_examples=200)
@given(page=_pages())
def test_property_17_redirect_chains_matches_threshold(
    page: CrawledPage,
) -> None:
    """For any redirect-chain hop count, ``check_redirect_chains`` emits a
    REDIRECT_CHAINS candidate iff ``hop_count >= REDIRECT_CHAIN_THRESHOLD``
    (including the exact boundary) and returns ``None`` otherwise.

    Feature: website-orchestrator-milestone-0, Property 17: Redirect-chain detection matches the hop threshold

    Validates: Requirements 4.6
    """
    hop_count = len(page.redirect_chain.hops)
    result = CheckEngine().check_redirect_chains(page)

    if hop_count >= REDIRECT_CHAIN_THRESHOLD:
        # At or above threshold (incl. hop_count == threshold): a well-formed
        # REDIRECT_CHAINS candidate is emitted.
        assert result is not None
        assert result.issue_type is IssueType.REDIRECT_CHAINS
        assert result.severity in _VALID_SEVERITIES
        assert result.description.strip() != ""
        assert result.detail.page_url == page.url
    else:
        # Below threshold: no issue.
        assert result is None
