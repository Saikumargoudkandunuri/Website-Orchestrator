"""Property test for the ``max_pages`` retrieval bound (task 5.7).

Feature: website-orchestrator-milestone-0, Property 2: Retrieved page count is
bounded by max_pages.

**Validates: Requirements 1.1, 1.4**

Property 2 states that for any fixture site — a generated set of interlinked
same-domain pages — and any ``max_pages`` in ``[1, 10000]``, the number of pages
the Crawler retrieves is at most ``max_pages`` (Req 1.4), equals the number of
reachable in-domain pages when that is fewer (Req 1.1), and every returned
element is a :class:`core.types.CrawledPage`.

The fixture site is generated as a directed link graph over ``N`` same-domain
pages (``N`` varied). The set of pages the crawl *should* retrieve is exactly the
breadth-first reachable set from the start URL over that graph; the crawl stops
once it has retrieved ``max_pages`` pages. So the expected retrieved count is
``min(max_pages, reachable_count)``.

All retrieval goes through an in-memory fake fetcher with an allow-all robots
gate, a no-op sleep, and a zero rate-limit floor, so the run is deterministic and
never contacts a live site (Req 2.5).
"""

from __future__ import annotations

from collections import deque

import pytest
from hypothesis import given
from hypothesis import strategies as st

from core.types import CrawledPage

from crawler import Crawler, FetchResponse, RobotsGate

DOMAIN = "https://example.com"

# Keep sizes modest so 100+ examples stay fast: up to ~30 pages, max_pages up to
# ~50. max_pages stays well within the required [1, 10000] range.
MAX_SITE_PAGES = 30
MAX_MAX_PAGES = 50


class FakeFetcher:
    """In-memory :class:`crawler.fetcher.Fetcher` mapping URL -> HTML.

    Every generated page URL exists here, so retrieval never touches the network
    (Req 2.5). URLs outside the fixture return 404 with empty HTML, but the
    generated link graph only ever points at in-fixture pages.
    """

    def __init__(self, pages: dict[str, str]) -> None:
        self._pages = pages
        self.requested: list[str] = []

    def fetch(self, url: str) -> FetchResponse:
        self.requested.append(url)
        html = self._pages.get(url, "")
        status = 200 if url in self._pages else 404
        return FetchResponse(url=url, final_url=url, status_code=status, html=html)


def _allow_all_gate() -> RobotsGate:
    """A network-free :class:`RobotsGate` whose empty robots.txt allows every URL."""
    return RobotsGate(lambda _robots_url: "")


def _url(index: int) -> str:
    """Stable, already-normalized URL for page ``index`` on the fixture domain."""
    return f"{DOMAIN}/p{index}"


def _page_html(targets: list[int]) -> str:
    """Render a page whose body links to each target page index (same domain)."""
    anchors = "".join(f'<a href="{_url(t)}">x</a>' for t in targets)
    return f"<html><head><title>T</title></head><body>{anchors}</body></html>"


def _reachable_count(adjacency: list[list[int]]) -> int:
    """Number of pages reachable from page 0 via BFS over the link graph.

    This mirrors exactly what the Crawler discovers: starting at ``_url(0)`` and
    following only in-domain links it has not seen before.
    """
    seen: set[int] = {0}
    queue: deque[int] = deque([0])
    while queue:
        node = queue.popleft()
        for target in adjacency[node]:
            if target not in seen:
                seen.add(target)
                queue.append(target)
    return len(seen)


@st.composite
def _fixture_site(draw: st.DrawFn) -> tuple[list[list[int]], int]:
    """Generate an interlinked same-domain fixture site and a ``max_pages`` value.

    Returns the adjacency list (page index -> list of linked page indices) plus a
    ``max_pages`` in ``[1, MAX_MAX_PAGES]`` (well within the required [1, 10000]).
    """
    n = draw(st.integers(min_value=1, max_value=MAX_SITE_PAGES))
    # Each page links to an arbitrary subset (with possible repeats/self-links,
    # which the crawl naturally de-duplicates) of the other pages.
    adjacency = [
        draw(st.lists(st.integers(min_value=0, max_value=n - 1), max_size=n))
        for _ in range(n)
    ]
    max_pages = draw(st.integers(min_value=1, max_value=MAX_MAX_PAGES))
    return adjacency, max_pages


@pytest.mark.property
@given(_fixture_site())
def test_retrieved_page_count_is_bounded_by_max_pages(
    site: tuple[list[list[int]], int],
) -> None:
    """Retrieved count == min(max_pages, reachable) and every item is CrawledPage.

    Feature: website-orchestrator-milestone-0, Property 2: Retrieved page count
    is bounded by max_pages. **Validates: Requirements 1.1, 1.4**
    """
    adjacency, max_pages = site

    pages_html = {_url(i): _page_html(targets) for i, targets in enumerate(adjacency)}
    fetcher = FakeFetcher(pages_html)
    crawler = Crawler(
        fetcher,
        robots_gate=_allow_all_gate(),
        sleep=lambda _seconds: None,
        rate_limit_ms=0,
    )

    result = crawler.crawl_site(_url(0), max_pages)

    reachable = _reachable_count(adjacency)
    expected = min(max_pages, reachable)

    # Req 1.4: never more than max_pages; Req 1.1: equals reachable when fewer.
    assert len(result) == expected
    # Never exceeds the bound, independent of the reachable computation.
    assert len(result) <= max_pages
    # Req 1.1: every returned element is a CrawledPage.
    assert all(isinstance(p, CrawledPage) for p in result)
    # Reinforcement: retrieved URLs are distinct and all within the fixture set.
    retrieved_urls = [p.url for p in result]
    assert len(retrieved_urls) == len(set(retrieved_urls))
    assert set(retrieved_urls) <= set(pages_html)
