"""Property test for redirect-chain recording (task 5.12).

Feature: website-orchestrator-milestone-0, Property 7: Recorded redirect chain
equals the actual traversal.

**Validates: Requirements 2.1**

Property 7 states that for any URL reachable through a sequence of HTTP redirects
(status in {301, 302, 303, 307, 308}) whose length stays below the redirect hard
cap, the crawler records the *whole* traversal: ``RedirectChain.hops`` equals the
ordered list of URLs actually visited (start, each intermediate, final) rather
than only a silently-followed final URL, ``final_url`` is the terminal page, and
``truncated`` is False because the chain fit under the cap.

The chain is generated as ``K`` single-hop redirects (``K`` varied, kept below
the default cap of 10) with each hop's status drawn from the redirect set, plus a
terminal 200 page. It is served by an in-memory single-hop
:class:`crawler.fetcher.Fetcher` (mirroring ``test_redirect_unit``'s
``HopFetcher``) that never follows redirects itself — walking and recording the
chain is the crawler's job — so the run is deterministic and never contacts a
live site (Req 2.5).
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from core.constants import REDIRECT_HARD_CAP

from crawler import Crawler, FetchResponse, RobotsGate

DOMAIN = "https://example.com"

REDIRECT_STATUSES = [301, 302, 303, 307, 308]

# Keep the generated chain strictly below the default hard cap (10) so the chain
# always terminates at a real page and is never truncated. K is the number of
# redirect hops; K in [1, 9] means the traversal has K + 1 URLs.
MAX_CHAIN_HOPS = REDIRECT_HARD_CAP - 1


class HopFetcher:
    """In-memory single-hop fetcher: URL -> one non-following response.

    Redirect entries carry a ``location`` and a redirect status; the terminal
    entry carries HTML and a 200. The fetcher never follows a redirect itself, so
    injecting this graph lets the crawler walk and record an arbitrary chain.
    """

    def __init__(self, responses: dict[str, FetchResponse]) -> None:
        self._responses = responses
        self.requested: list[str] = []

    def fetch(self, url: str) -> FetchResponse:
        self.requested.append(url)
        if url in self._responses:
            return self._responses[url]
        return FetchResponse(url=url, final_url=url, status_code=404, html="")


def _redirect(url: str, location: str, status: int) -> FetchResponse:
    """A single-hop redirect response for ``url`` pointing at ``location``."""
    return FetchResponse(
        url=url, final_url=url, status_code=status, html="", location=location
    )


def _page(url: str) -> FetchResponse:
    """A single-hop terminal (200) page response for ``url``."""
    return FetchResponse(
        url=url,
        final_url=url,
        status_code=200,
        html="<html><head><title>T</title></head><body>ok</body></html>",
    )


def _allow_all_gate() -> RobotsGate:
    """A network-free :class:`RobotsGate` whose empty robots.txt allows every URL."""
    return RobotsGate(lambda _robots_url: "")


@st.composite
def _redirect_chain(draw: st.DrawFn) -> tuple[list[str], list[int]]:
    """Generate a redirect chain below the cap.

    Returns ``(hops, statuses)`` where ``hops`` is the ordered list of URLs the
    crawler should traverse — ``[start, hop1, ..., final]`` with ``K + 1`` URLs
    for ``K`` redirects — and ``statuses`` is the per-hop redirect status
    (length ``K``), each drawn from {301, 302, 303, 307, 308}.
    """
    k = draw(st.integers(min_value=1, max_value=MAX_CHAIN_HOPS))
    hops = [f"{DOMAIN}/r{i}" for i in range(k + 1)]
    statuses = draw(
        st.lists(
            st.sampled_from(REDIRECT_STATUSES),
            min_size=k,
            max_size=k,
        )
    )
    return hops, statuses


@pytest.mark.property
@settings(max_examples=100)
@given(_redirect_chain())
def test_recorded_redirect_chain_equals_actual_traversal(
    chain: tuple[list[str], list[int]],
) -> None:
    """Recorded hops equal the full ordered traversal; final_url is terminal.

    Feature: website-orchestrator-milestone-0, Property 7: Recorded redirect chain
    equals the actual traversal. **Validates: Requirements 2.1**
    """
    hops, statuses = chain
    start, final = hops[0], hops[-1]

    # Build the single-hop graph: each URL redirects to its successor with the
    # generated status, and the final URL is a terminal 200 page.
    responses: dict[str, FetchResponse] = {
        hops[i]: _redirect(hops[i], hops[i + 1], status=statuses[i])
        for i in range(len(statuses))
    }
    responses[final] = _page(final)

    fetcher = HopFetcher(responses)
    crawler = Crawler(
        fetcher,
        robots_gate=_allow_all_gate(),
        sleep=lambda _seconds: None,
        rate_limit_ms=0,
    )

    # max_pages=1 isolates the start URL's chain: only the start page's redirect
    # traversal matters, so no other page's links perturb the recorded chain.
    pages = crawler.crawl_site(start, 1)

    page = next(p for p in pages if p.url == start)

    # Req 2.1: the recorded chain is the ordered list of URLs actually traversed
    # (start, each intermediate, final) — not just the silently-followed final.
    assert page.redirect_chain.hops == hops
    # Chain fit below the cap, so it is not truncated and ends at a real page.
    assert page.redirect_chain.truncated is False
    assert page.final_url == final
    assert page.status_code == 200
    # The crawler actually walked every hop (single-hop fetcher, no self-follow).
    assert fetcher.requested == hops
