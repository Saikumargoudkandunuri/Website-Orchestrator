"""Unit tests for redirect-chain recording and the redirect hard cap
(task 5.4, Req 2.1, 2.2).

The crawler's injected :class:`~crawler.fetcher.Fetcher` performs a single
request per call and never follows redirects; the crawler walks and records the
Redirect_Chain itself, bounded by a configurable hard cap. These tests inject an
in-memory fake fetcher that maps each URL to a single-hop response (a redirect
with a ``Location`` or a terminal page), so a whole chain — including one longer
than the cap or an infinite cycle — is simulated deterministically without ever
contacting the network (Req 2.5).
"""

from __future__ import annotations

import pytest

from core.constants import REDIRECT_HARD_CAP

from crawler import Crawler, FetchResponse, RobotsGate
from crawler.crawler import MAX_REDIRECT_CAP, MIN_REDIRECT_CAP


class HopFetcher:
    """In-memory single-hop fetcher: URL -> one non-following response.

    Each entry describes exactly one HTTP response. Redirect entries carry a
    ``location`` (the ``Location`` target) and a redirect status; terminal
    entries carry HTML and a 200. The fetcher never follows a redirect itself —
    that is the crawler's job — so injecting a graph of these responses
    simulates an arbitrary redirect chain.
    """

    def __init__(self, responses: dict[str, FetchResponse]) -> None:
        self._responses = responses
        self.requested: list[str] = []

    def fetch(self, url: str) -> FetchResponse:
        self.requested.append(url)
        if url in self._responses:
            return self._responses[url]
        # Unknown URL -> a terminal 404 (never a redirect).
        return FetchResponse(url=url, final_url=url, status_code=404, html="")


def _redirect(url: str, location: str, status: int = 301) -> FetchResponse:
    """A single-hop redirect response for ``url`` pointing at ``location``."""
    return FetchResponse(
        url=url, final_url=url, status_code=status, html="", location=location
    )


def _page(url: str, html: str = "<html><head><title>T</title></head><body>ok</body></html>") -> FetchResponse:
    """A single-hop terminal (200) page response for ``url``."""
    return FetchResponse(url=url, final_url=url, status_code=200, html=html)


def _allow_all_gate() -> RobotsGate:
    """A network-free robots gate whose empty robots.txt allows every URL."""
    return RobotsGate(lambda _robots_url: "")


def _crawler(fetcher: HopFetcher, **kwargs) -> Crawler:
    # Disable the per-host delay and use a no-op sleep so walking a multi-hop
    # chain (each hop is same-host and would otherwise be paced) stays fast and
    # never touches wall-clock waiting. Pacing itself is covered by task 5.3's
    # dedicated tests.
    kwargs.setdefault("rate_limit_ms", 0)
    return Crawler(
        fetcher,
        robots_gate=_allow_all_gate(),
        sleep=lambda _seconds: None,
        **kwargs,
    )


# --- Redirect-chain recording (Req 2.1) --------------------------------------


@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
def test_single_redirect_status_is_recorded_in_order(status):
    start = "https://example.com/old"
    dest = "https://example.com/new"
    fetcher = HopFetcher(
        {
            start: _redirect(start, dest, status=status),
            dest: _page(dest),
        }
    )
    crawler = _crawler(fetcher)

    pages = crawler.crawl_site(start, 5)

    page = next(p for p in pages if p.url == start)
    # The recorded chain is the ordered list of URLs actually traversed.
    assert page.redirect_chain.hops == [start, dest]
    assert page.redirect_chain.truncated is False
    assert page.final_url == dest
    assert page.status_code == 200


def test_multi_hop_redirect_chain_is_recorded_in_traversal_order():
    a = "https://example.com/a"
    b = "https://example.com/b"
    c = "https://example.com/c"
    d = "https://example.com/d"
    fetcher = HopFetcher(
        {
            a: _redirect(a, b, status=301),
            b: _redirect(b, c, status=302),
            c: _redirect(c, d, status=307),
            d: _page(d),
        }
    )
    crawler = _crawler(fetcher)

    pages = crawler.crawl_site(a, 5)

    page = next(p for p in pages if p.url == a)
    assert page.redirect_chain.hops == [a, b, c, d]
    assert page.redirect_chain.truncated is False
    assert page.final_url == d


def test_no_redirect_yields_empty_chain():
    start = "https://example.com/"
    fetcher = HopFetcher({start: _page(start)})
    crawler = _crawler(fetcher)

    pages = crawler.crawl_site(start, 5)

    page = pages[0]
    assert page.redirect_chain.hops == []
    assert page.redirect_chain.truncated is False


def test_relative_location_is_resolved_against_current_url():
    start = "https://example.com/old"
    dest = "https://example.com/new"
    fetcher = HopFetcher(
        {
            # Location header is a relative path; the crawler resolves it.
            start: _redirect(start, "/new", status=302),
            dest: _page(dest),
        }
    )
    crawler = _crawler(fetcher)

    pages = crawler.crawl_site(start, 5)

    page = next(p for p in pages if p.url == start)
    assert page.redirect_chain.hops == [start, dest]


# --- Redirect hard cap (Req 2.2) ---------------------------------------------


def _infinite_chain_fetcher() -> HopFetcher:
    """A fetcher where every URL redirects to the next, forever (a cycle)."""

    class _Cycle(HopFetcher):
        def fetch(self, url: str) -> FetchResponse:
            self.requested.append(url)
            # Every URL redirects to a fresh successor -> unbounded chain.
            nxt = url + "x"
            return _redirect(url, nxt, status=301)

    return _Cycle({})


def test_chain_longer_than_cap_stops_and_is_marked_truncated():
    cap = 3
    fetcher = _infinite_chain_fetcher()
    crawler = _crawler(fetcher, redirect_hard_cap=cap)

    start = "https://example.com/r"
    pages = crawler.crawl_site(start, 1)

    page = pages[0]
    # Followed exactly `cap` redirects then stopped: the recorded chain has
    # cap + 1 URLs (start plus cap targets) and is marked truncated.
    assert page.redirect_chain.truncated is True
    assert len(page.redirect_chain.hops) == cap + 1
    assert page.redirect_chain.hops[0] == start
    # Loop is bounded: the number of fetches never runs away.
    assert len(fetcher.requested) == cap + 1


def test_chain_exactly_at_cap_terminating_is_not_truncated():
    cap = 3
    # start -> h1 -> h2 -> h3(terminal). Exactly `cap` redirects, then a page.
    urls = [f"https://example.com/h{i}" for i in range(cap + 1)]
    responses: dict[str, FetchResponse] = {}
    for i in range(cap):
        responses[urls[i]] = _redirect(urls[i], urls[i + 1], status=301)
    responses[urls[cap]] = _page(urls[cap])
    fetcher = HopFetcher(responses)
    crawler = _crawler(fetcher, redirect_hard_cap=cap)

    pages = crawler.crawl_site(urls[0], 1)

    page = pages[0]
    assert page.redirect_chain.truncated is False
    assert page.redirect_chain.hops == urls
    assert page.final_url == urls[cap]


def test_default_cap_is_ten():
    fetcher = _infinite_chain_fetcher()
    crawler = _crawler(fetcher)  # default cap

    start = "https://example.com/r"
    pages = crawler.crawl_site(start, 1)

    page = pages[0]
    assert page.redirect_chain.truncated is True
    # Default REDIRECT_HARD_CAP = 10 -> 10 redirects followed, 11 URLs recorded.
    assert REDIRECT_HARD_CAP == 10
    assert len(page.redirect_chain.hops) == REDIRECT_HARD_CAP + 1


# --- Cap configuration and bounds [1, 50] ------------------------------------


@pytest.mark.parametrize(
    "requested, effective",
    [
        (0, MIN_REDIRECT_CAP),      # below the lower bound -> clamped up to 1
        (-5, MIN_REDIRECT_CAP),     # negative -> clamped up to 1
        (1, 1),                     # lower bound accepted as-is
        (25, 25),                   # in range accepted as-is
        (50, 50),                   # upper bound accepted as-is
        (51, MAX_REDIRECT_CAP),     # above the upper bound -> clamped to 50
        (1000, MAX_REDIRECT_CAP),   # far above -> clamped to 50
    ],
)
def test_cap_is_configurable_and_clamped_to_bounds(requested, effective):
    fetcher = _infinite_chain_fetcher()
    crawler = _crawler(fetcher, redirect_hard_cap=requested)

    start = "https://example.com/r"
    pages = crawler.crawl_site(start, 1)

    page = pages[0]
    # Whatever cap was requested, the effective (clamped) value bounds the walk:
    # `effective` redirects are followed and the chain is truncated.
    assert page.redirect_chain.truncated is True
    assert len(page.redirect_chain.hops) == effective + 1
    assert len(fetcher.requested) == effective + 1
