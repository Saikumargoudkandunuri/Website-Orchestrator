"""Unit tests for the Crawler skeleton (task 5.1).

Covers input validation (Req 1.5), same-domain retrieval (Req 1.2, 1.3), the
``max_pages`` bound (Req 1.1, 1.4), and that a ``list[CrawledPage]`` is returned.
All retrieval goes through an in-memory fake fetcher, so no live site is ever
contacted (Req 2.5).
"""

from __future__ import annotations

import pytest

from core.exceptions import InvalidCrawlRequest
from core.types import CrawledPage

from crawler import Crawler, FetchResponse, RobotsGate


class FakeFetcher:
    """In-memory :class:`crawler.fetcher.Fetcher` mapping URL -> FetchResponse."""

    def __init__(self, pages: dict[str, str]) -> None:
        # pages: normalized_url -> html
        self._pages = pages
        self.requested: list[str] = []

    def fetch(self, url: str) -> FetchResponse:
        self.requested.append(url)
        html = self._pages.get(url, "")
        status = 200 if url in self._pages else 404
        return FetchResponse(
            url=url, final_url=url, status_code=status, html=html
        )


def _allow_all_gate() -> RobotsGate:
    """A network-free :class:`RobotsGate` whose empty robots.txt allows every URL.

    An empty ``robots.txt`` body carries no ``Disallow`` rules, so the gate
    permits all URLs — isolating these 5.1 tests from robots.txt gating while
    keeping the run network-free.
    """
    return RobotsGate(lambda _robots_url: "")


def _crawler(fetcher: FakeFetcher) -> Crawler:
    """Build a Crawler with the fake fetcher and an allow-all robots gate.

    A no-op sleep is injected so multi-page same-host crawls do not incur the
    real per-host pacing delay (the default 1 s floor). These 5.1 tests assert
    retrieval/validation behavior, not timing, so skipping the wall-clock wait
    preserves what they verify while keeping them fast and deterministic. Pacing
    timing itself is covered by the rate-limit tests with an explicit fake clock.
    """
    return Crawler(
        fetcher, robots_gate=_allow_all_gate(), sleep=lambda _seconds: None
    )


def _page(links: list[str] = (), extra: str = "") -> str:
    anchors = "".join(f'<a href="{href}">x</a>' for href in links)
    return f"<html><head><title>T</title></head><body>{anchors}{extra}</body></html>"


# --- Input validation (Req 1.5) ----------------------------------------------


@pytest.mark.parametrize(
    "bad_url",
    [
        "",
        "   ",
        "not-a-url",
        "ftp://example.com",
        "example.com",  # no scheme
        "http://",  # no host
        "//example.com",  # scheme-relative, no scheme
        123,
        None,
    ],
)
def test_malformed_start_url_raises_and_retrieves_nothing(bad_url):
    fetcher = FakeFetcher({})
    crawler = _crawler(fetcher)
    with pytest.raises(InvalidCrawlRequest):
        crawler.crawl_site(bad_url, 10)
    assert fetcher.requested == []


@pytest.mark.parametrize("bad_pages", [0, -1, 10001, 100000, True, False, 1.5, "5"])
def test_out_of_range_max_pages_raises_and_retrieves_nothing(bad_pages):
    fetcher = FakeFetcher({"https://example.com": _page()})
    crawler = _crawler(fetcher)
    with pytest.raises(InvalidCrawlRequest):
        crawler.crawl_site("https://example.com", bad_pages)
    assert fetcher.requested == []


@pytest.mark.parametrize("good_pages", [1, 10, 10000])
def test_boundary_max_pages_accepted(good_pages):
    fetcher = FakeFetcher({"https://example.com": _page()})
    crawler = _crawler(fetcher)
    result = crawler.crawl_site("https://example.com", good_pages)
    assert isinstance(result, list)
    assert all(isinstance(p, CrawledPage) for p in result)


# --- Retrieval behavior -------------------------------------------------------


def test_returns_crawled_pages_and_parses_content():
    url = "https://example.com"
    fetcher = FakeFetcher({url: _page(extra="one two three four five")})
    crawler = _crawler(fetcher)

    pages = crawler.crawl_site(url, 5)

    assert len(pages) == 1
    page = pages[0]
    assert isinstance(page, CrawledPage)
    assert page.url == url
    assert page.status_code == 200
    assert page.title == "T"
    assert page.word_count >= 5
    assert page.crawled_at is not None


def test_follows_same_domain_links_only():
    base = "https://example.com"
    pages_html = {
        base: _page(
            links=[
                "https://example.com/a",
                "https://sub.example.com/b",  # same registrable domain
                "https://other.org/c",  # out of domain -> excluded
            ]
        ),
        "https://example.com/a": _page(),
        "https://sub.example.com/b": _page(),
    }
    fetcher = FakeFetcher(pages_html)
    crawler = _crawler(fetcher)

    pages = crawler.crawl_site(base, 100)
    retrieved = {p.url for p in pages}

    assert base in retrieved
    assert "https://example.com/a" in retrieved
    assert "https://sub.example.com/b" in retrieved
    # Out-of-domain URL is never retrieved (Req 1.3).
    assert "https://other.org/c" not in retrieved
    assert all("other.org" not in u for u in fetcher.requested)


def test_stops_at_max_pages():
    base = "https://example.com"
    # Chain of in-domain pages, each linking to the next.
    urls = [f"https://example.com/p{i}" for i in range(20)]
    html = {base: _page(links=[urls[0]])}
    for i, u in enumerate(urls):
        nxt = urls[i + 1] if i + 1 < len(urls) else None
        html[u] = _page(links=[nxt] if nxt else [])
    fetcher = FakeFetcher(html)
    crawler = _crawler(fetcher)

    pages = crawler.crawl_site(base, 5)

    assert len(pages) == 5


def test_no_duplicate_retrieval():
    base = "https://example.com"
    html = {
        base: _page(links=["https://example.com/a", "https://example.com/a"]),
        "https://example.com/a": _page(links=[base]),
    }
    fetcher = FakeFetcher(html)
    crawler = _crawler(fetcher)

    pages = crawler.crawl_site(base, 100)

    assert len(pages) == 2
    assert len(fetcher.requested) == 2

