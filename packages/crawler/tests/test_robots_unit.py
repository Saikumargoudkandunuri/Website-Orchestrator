"""Unit tests for robots.txt fail-closed gating (task 5.2, Req 1.6-1.8).

The Crawler must consult each origin's ``robots.txt`` before retrieving any URL
(Req 1.6). A URL the ``robots.txt`` disallows is excluded (Req 1.8); a URL whose
``robots.txt`` cannot be retrieved is excluded by failing closed (Req 1.7). All
robots.txt and page retrieval goes through in-memory fakes, so no live site is
ever contacted (Req 2.5).

Every Crawler here is built with a no-op ``sleep`` so multi-page same-host
crawls skip the real per-host pacing delay (the default 1 s floor). These tests
assert robots gating behavior, not timing, so eliding the wall-clock wait
preserves exactly what they verify while keeping them fast and non-flaky. Pacing
timing itself is covered by the rate-limit tests using an explicit fake clock.
"""

from __future__ import annotations

import pytest

from core.exceptions import RobotsUnavailableError

from crawler import Crawler, FetchResponse, RobotsGate


class FakeFetcher:
    """In-memory :class:`crawler.fetcher.Fetcher` mapping URL -> html."""

    def __init__(self, pages: dict[str, str]) -> None:
        self._pages = pages
        self.requested: list[str] = []

    def fetch(self, url: str) -> FetchResponse:
        self.requested.append(url)
        html = self._pages.get(url, "")
        status = 200 if url in self._pages else 404
        return FetchResponse(url=url, final_url=url, status_code=status, html=html)


class FakeRobotsFetcher:
    """In-memory robots.txt fetcher: robots_url -> body, or raise if unavailable.

    A ``robots.txt`` URL mapped to ``None`` (or simply absent when
    ``strict`` is set) simulates an unretrievable document by raising, exercising
    the fail-closed path (Req 1.7).
    """

    def __init__(self, bodies: dict[str, str | None]) -> None:
        self._bodies = bodies
        self.requested: list[str] = []

    def __call__(self, robots_url: str) -> str:
        self.requested.append(robots_url)
        body = self._bodies.get(robots_url, None)
        if body is None:
            raise ConnectionError(f"robots.txt unavailable: {robots_url}")
        return body


def _page(links: list[str] = ()) -> str:
    anchors = "".join(f'<a href="{href}">x</a>' for href in links)
    return f"<html><head><title>T</title></head><body>{anchors}</body></html>"


def _robots(disallow: list[str]) -> str:
    lines = ["User-agent: *"]
    lines += [f"Disallow: {path}" for path in disallow]
    return "\n".join(lines)


# --- Disallowed URL is excluded (Req 1.8) ------------------------------------


def test_disallowed_url_is_excluded_but_allowed_ones_retrieved():
    base = "https://example.com"
    pages = {
        base: _page(links=[f"{base}/public", f"{base}/private"]),
        f"{base}/public": _page(),
        f"{base}/private": _page(),
    }
    fetcher = FakeFetcher(pages)
    robots = FakeRobotsFetcher(
        {"https://example.com/robots.txt": _robots(disallow=["/private"])}
    )
    crawler = Crawler(
        fetcher, robots_gate=RobotsGate(robots), sleep=lambda _seconds: None
    )

    retrieved = {p.url for p in crawler.crawl_site(base, 100)}

    assert base in retrieved
    assert f"{base}/public" in retrieved
    # Disallowed URL is never passed to the page fetcher (Req 1.8).
    assert f"{base}/private" not in retrieved
    assert f"{base}/private" not in fetcher.requested


# --- robots.txt unavailable -> fail closed (Req 1.7) -------------------------


def test_robots_unavailable_fails_closed_excludes_url():
    base = "https://example.com"
    fetcher = FakeFetcher({base: _page()})
    # No robots.txt body registered -> the fetcher raises -> fail closed.
    robots = FakeRobotsFetcher({})
    crawler = Crawler(
        fetcher, robots_gate=RobotsGate(robots), sleep=lambda _seconds: None
    )

    pages = crawler.crawl_site(base, 100)

    assert pages == []
    # The unretrievable-robots URL is never passed to the page fetcher.
    assert fetcher.requested == []


def test_robots_unavailable_excludes_only_affected_origin():
    base = "https://example.com"
    other = "https://elsewhere.com"
    pages = {
        base: _page(links=[f"{other}/ok"]),
        f"{other}/ok": _page(),
    }
    fetcher = FakeFetcher(pages)
    # example.com robots.txt is retrievable & permissive; elsewhere.com is not.
    # (elsewhere.com is out of the start domain, so it is never enqueued anyway;
    # this guards that a missing robots.txt does not crash the whole crawl.)
    robots = FakeRobotsFetcher({"https://example.com/robots.txt": _robots([])})
    crawler = Crawler(
        fetcher, robots_gate=RobotsGate(robots), sleep=lambda _seconds: None
    )

    retrieved = {p.url for p in crawler.crawl_site(base, 100)}

    # The start origin (retrievable robots) is crawled; the crawl does not crash.
    assert base in retrieved


# --- Allowed URL is retrieved (Req 1.6) --------------------------------------


def test_allowed_url_is_retrieved():
    base = "https://example.com"
    fetcher = FakeFetcher({base: _page()})
    robots = FakeRobotsFetcher(
        {"https://example.com/robots.txt": _robots(disallow=["/other"])}
    )
    crawler = Crawler(
        fetcher, robots_gate=RobotsGate(robots), sleep=lambda _seconds: None
    )

    pages = crawler.crawl_site(base, 100)

    assert len(pages) == 1
    assert pages[0].url == base


# --- start_url disallowed -> nothing retrieved (Req 1.6, 1.8) ----------------


def test_start_url_disallowed_retrieves_nothing():
    base = "https://example.com/blocked"
    fetcher = FakeFetcher({base: _page()})
    robots = FakeRobotsFetcher(
        {"https://example.com/robots.txt": _robots(disallow=["/blocked"])}
    )
    crawler = Crawler(
        fetcher, robots_gate=RobotsGate(robots), sleep=lambda _seconds: None
    )

    pages = crawler.crawl_site(base, 100)

    assert pages == []
    assert fetcher.requested == []


# --- robots.txt is consulted before fetching and cached per origin -----------


def test_robots_is_consulted_once_per_origin():
    base = "https://example.com"
    pages = {
        base: _page(links=[f"{base}/a", f"{base}/b"]),
        f"{base}/a": _page(),
        f"{base}/b": _page(),
    }
    fetcher = FakeFetcher(pages)
    robots = FakeRobotsFetcher({"https://example.com/robots.txt": _robots([])})
    crawler = Crawler(
        fetcher, robots_gate=RobotsGate(robots), sleep=lambda _seconds: None
    )

    crawler.crawl_site(base, 100)

    # Three same-origin URLs, but robots.txt fetched at most once (cached).
    assert robots.requested == ["https://example.com/robots.txt"]


# --- RobotsGate unit-level behavior ------------------------------------------


def test_gate_allows_when_robots_permits():
    gate = RobotsGate(lambda _url: _robots(disallow=["/private"]))
    assert gate.allowed("https://example.com/public") is True


def test_gate_disallows_matching_path():
    gate = RobotsGate(lambda _url: _robots(disallow=["/private"]))
    assert gate.allowed("https://example.com/private") is False


def test_gate_fails_closed_when_fetcher_raises():
    def _boom(_url: str) -> str:
        raise ConnectionError("no robots")

    gate = RobotsGate(_boom)
    assert gate.allowed("https://example.com/anything") is False


def test_gate_empty_robots_allows_all():
    gate = RobotsGate(lambda _url: "")
    assert gate.allowed("https://example.com/anything") is True


def test_gate_fails_closed_for_unusable_url():
    gate = RobotsGate(lambda _url: "")
    # No scheme/netloc -> no origin to consult -> fail closed.
    assert gate.allowed("not-a-url") is False
