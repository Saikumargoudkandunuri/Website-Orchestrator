"""Property 4 — Robots-excluded URLs are never retrieved.

Feature: website-orchestrator-milestone-0, Property 4: Robots-excluded URLs are
never retrieved.

**Validates: Requirements 1.6, 1.7, 1.8**

Before the :class:`~crawler.crawler.Crawler` retrieves any URL it consults the
origin's ``robots.txt`` and honors its directives (Req 1.6). Two exclusions must
hold for *any* ruleset and *any* set of candidate same-domain URLs:

* A URL that ``robots.txt`` **disallows** is never retrieved (Req 1.8).
* When ``robots.txt`` **cannot be retrieved**, the crawl fails closed and
  excludes the affected URLs entirely — nothing on that origin is fetched
  (Req 1.7).

This property builds a start page that links to a generated set of same-domain
paths, marks a generated subset of them ``Disallow`` in ``robots.txt``, and
optionally simulates an unretrievable ``robots.txt`` for the whole run. A
recording page-fetcher captures every fetch actually attempted. The expected
retrievable set is computed independently (the allowed same-domain paths plus
the start page), and the test asserts the retrieved set is a subset of the
allowed set and disjoint from the disallowed set — and, in the unavailable case,
that the page-fetcher recorded zero requests. Everything goes through in-memory
fakes, so no live site is ever contacted (Req 2.5).
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from crawler import Crawler, FetchResponse, RobotsGate

BASE = "https://example.com"
ROBOTS_URL = "https://example.com/robots.txt"


class RecordingFetcher:
    """In-memory :class:`crawler.fetcher.Fetcher` that records every request.

    Maps a (normalized) URL to its HTML body; an unknown URL yields a 404 with
    an empty body. ``requested`` preserves the order of every fetch attempted,
    so a test can assert that a disallowed (or robots-unavailable) URL was never
    passed to the page fetcher.
    """

    def __init__(self, pages: dict[str, str]) -> None:
        self._pages = pages
        self.requested: list[str] = []

    def fetch(self, url: str) -> FetchResponse:
        self.requested.append(url)
        html = self._pages.get(url, "")
        status = 200 if url in self._pages else 404
        return FetchResponse(url=url, final_url=url, status_code=status, html=html)


class FakeRobotsFetcher:
    """robots.txt fetcher: returns a fixed body, or raises to fail closed.

    When ``unavailable`` is set the fetcher raises on every call, simulating a
    ``robots.txt`` that cannot be retrieved (Req 1.7). Otherwise it returns the
    single robots body for the origin.
    """

    def __init__(self, body: str, *, unavailable: bool) -> None:
        self._body = body
        self._unavailable = unavailable
        self.requested: list[str] = []

    def __call__(self, robots_url: str) -> str:
        self.requested.append(robots_url)
        if self._unavailable:
            raise ConnectionError(f"robots.txt unavailable: {robots_url}")
        return self._body


def _path_for(i: int) -> str:
    """Return a fixed-width same-domain path for id ``i``.

    Fixed width plus no trailing slash guarantees that no generated path is a
    prefix of another, so a ``Disallow`` on one path can never accidentally
    match a different one under ``robots.txt`` prefix-matching semantics.
    """
    return f"/p{i:03d}"


def _start_page(paths: list[str]) -> str:
    """Return start-page HTML linking to every candidate same-domain path."""
    anchors = "".join(f'<a href="{BASE}{p}">x</a>' for p in paths)
    return f"<html><head><title>T</title></head><body>{anchors}</body></html>"


def _leaf_page() -> str:
    return "<html><head><title>L</title></head><body>leaf</body></html>"


def _robots(disallow: list[str]) -> str:
    lines = ["User-agent: *"]
    lines += [f"Disallow: {path}" for path in disallow]
    return "\n".join(lines)


# One entry per candidate path: (id, is_disallowed). ``unique_by`` on the id
# keeps the paths distinct; up to 12 candidates keeps each example small while
# still exercising mixed allowed/disallowed rulesets.
_entries = st.lists(
    st.tuples(st.integers(min_value=0, max_value=999), st.booleans()),
    unique_by=lambda entry: entry[0],
    max_size=12,
)


@settings(max_examples=200)
@given(entries=_entries, robots_unavailable=st.booleans())
def test_robots_excluded_urls_are_never_retrieved(
    entries: list[tuple[int, bool]], robots_unavailable: bool
) -> None:
    """Retrieved set ⊆ allowed, disjoint from disallowed; nothing when closed.

    **Validates: Requirements 1.6, 1.7, 1.8**
    """
    paths = [_path_for(i) for i, _ in entries]
    disallowed_paths = [_path_for(i) for i, disallow in entries if disallow]

    # Build the fixture site: start page links to every candidate; each
    # candidate resolves to a leaf page.
    pages: dict[str, str] = {BASE: _start_page(paths)}
    for path in paths:
        pages[BASE + path] = _leaf_page()
    fetcher = RecordingFetcher(pages)

    robots = FakeRobotsFetcher(
        _robots(disallowed_paths), unavailable=robots_unavailable
    )
    # Inject a no-op sleep so per-host pacing runs its logic without a real
    # wall-clock wait. This property asserts *which* URLs are retrieved (robots
    # exclusion), not timing, so skipping the actual delay preserves the
    # behavior under test while keeping the run fast and non-flaky. (Rate-limit
    # floor and degradation timing are covered by properties 5 and 6 with an
    # explicit fake clock.)
    crawler = Crawler(
        fetcher, robots_gate=RobotsGate(robots), sleep=lambda _seconds: None
    )

    retrieved = {page.url for page in crawler.crawl_site(BASE, 1000)}

    # Independently computed expectation.
    disallowed_urls = {BASE + p for p in disallowed_paths}
    allowed_urls = {BASE} | {BASE + p for p in paths if p not in set(disallowed_paths)}

    if robots_unavailable:
        # Fail closed: robots.txt for the origin cannot be retrieved, so NOTHING
        # on that origin is retrieved — not even the start page (Req 1.7).
        assert retrieved == set()
        assert fetcher.requested == []
        return

    # A disallowed URL is never retrieved and never even passed to the page
    # fetcher (Req 1.8).
    assert retrieved.isdisjoint(disallowed_urls)
    for url in disallowed_urls:
        assert url not in fetcher.requested

    # Every retrieved URL is one robots.txt permits (Req 1.6). The start page is
    # allowed (no Disallow matches it), so the two sets are exactly equal here,
    # but subset is the invariant that must always hold.
    assert retrieved <= allowed_urls
    assert retrieved == allowed_urls
