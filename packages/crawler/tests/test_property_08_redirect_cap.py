"""Property test for the redirect hard cap (task 5.13).

Feature: website-orchestrator-milestone-0, Property 8: Redirect chains are
bounded by the hard cap.

**Validates: Requirements 2.2**

Property 8 states that for any redirect sequence longer than the configured hard
cap — default 10, configurable within the bounds ``[1, 50]`` — the crawler stops
following at the (clamped) cap, records the chain up to the cap (``start`` plus
``cap`` targets, i.e. ``cap + 1`` hops), marks the recorded chain
``truncated=True``, and never loops indefinitely.

The redirect chain is simulated by an in-memory single-hop fetcher where *every*
URL redirects to a fresh successor, producing an unbounded (effectively
infinite) chain. Whatever cap is requested — including out-of-range values that
must be clamped to ``[1, 50]`` — the effective cap must bound both the recorded
hops and the number of fetches, proving the walk terminates. All retrieval goes
through the fake fetcher with an allow-all robots gate, a no-op sleep, and a
zero rate-limit floor, so the run is deterministic and never contacts a live
site (Req 2.5).
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from crawler import Crawler, FetchResponse, RobotsGate
from crawler.crawler import MAX_REDIRECT_CAP, MIN_REDIRECT_CAP

START = "https://example.com/r"


class InfiniteChainFetcher:
    """Single-hop fetcher where every URL redirects to a fresh successor.

    Because every response is a redirect to a brand-new URL, the chain never
    terminates on its own — only the crawler's hard cap can stop the walk. The
    ``requested`` list records every fetch so the test can assert the loop is
    bounded (never runs away).
    """

    def __init__(self) -> None:
        self.requested: list[str] = []

    def fetch(self, url: str) -> FetchResponse:
        self.requested.append(url)
        # Every URL redirects to a fresh successor -> unbounded chain.
        return FetchResponse(
            url=url, final_url=url, status_code=301, html="", location=url + "x"
        )


def _allow_all_gate() -> RobotsGate:
    """A network-free :class:`RobotsGate` whose empty robots.txt allows every URL."""
    return RobotsGate(lambda _robots_url: "")


def _effective_cap(requested: int) -> int:
    """The cap the crawler actually enforces: ``requested`` clamped to [1, 50]."""
    return max(MIN_REDIRECT_CAP, min(MAX_REDIRECT_CAP, requested))


# Cover in-range caps plus out-of-range values (0, negative, > 50) that must be
# clamped to the [1, 50] bounds. The floor/ceiling of the sampled range extend
# past the bounds so clamping is exercised on both sides.
_cap_strategy = st.integers(min_value=-10, max_value=60)


@pytest.mark.property
@given(requested_cap=_cap_strategy)
def test_redirect_chain_is_bounded_by_the_hard_cap(requested_cap: int) -> None:
    """An unbounded redirect chain is truncated at the clamped hard cap.

    Feature: website-orchestrator-milestone-0, Property 8: Redirect chains are
    bounded by the hard cap. **Validates: Requirements 2.2**
    """
    fetcher = InfiniteChainFetcher()
    crawler = Crawler(
        fetcher,
        robots_gate=_allow_all_gate(),
        sleep=lambda _seconds: None,
        rate_limit_ms=0,
        redirect_hard_cap=requested_cap,
    )

    pages = crawler.crawl_site(START, 1)

    effective = _effective_cap(requested_cap)

    # Exactly one page is retrieved (max_pages == 1) and it is the start URL.
    assert len(pages) == 1
    page = pages[0]

    # The chain was cut short at the cap, so it is marked truncated.
    assert page.redirect_chain.truncated is True

    # Records the chain up to the cap: start plus `effective` targets.
    assert len(page.redirect_chain.hops) == effective + 1
    assert page.redirect_chain.hops[0] == START

    # The walk never loops indefinitely: the fetcher is invoked exactly
    # `effective + 1` times (start + one fetch per followed redirect).
    assert len(fetcher.requested) == effective + 1

    # The effective cap always sits within the configured [1, 50] bounds,
    # regardless of the (possibly out-of-range) requested value.
    assert MIN_REDIRECT_CAP <= effective <= MAX_REDIRECT_CAP
