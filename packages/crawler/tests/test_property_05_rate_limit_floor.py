"""Property 5 — Rate-limit delay floor is never violated.

Feature: website-orchestrator-milestone-0, Property 5: Rate-limit delay floor is
never violated.

**Validates: Requirements 1.9, 1.10**

The configured ``Rate_Limit`` is a hard per-host floor that is treated as a
correctness constraint and is *never* reduced to crawl faster (Req 1.9, 1.10).
This property asserts that, for *any* chain of same-host pages and *any*
configured floor, the delay the crawler enforces between two consecutive
requests to that host is always at least the configured floor.

The crawl is driven by an injected fake clock plus a recording sleep, so timing
is deterministic and no live site is ever contacted (Req 2.5). Responses are
kept fast (0 s, well below the degradation threshold) so no doubling is
triggered — under that regime the enforced delay sits exactly at the floor, and
``sleep >= floor`` is the invariant that must hold. The first request to a host
is never delayed, so ``N`` retrieved same-host pages produce exactly ``N - 1``
enforced delays.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from hypothesis import given, settings
from hypothesis import strategies as st

from core.constants import DEGRADATION_THRESHOLD_MS

from crawler import Crawler, FetchResponse, RobotsGate

BASE = "https://example.com"


class FakeClock:
    """Deterministic injectable clock plus a recording sleep.

    ``now()`` returns the current simulated UTC time. ``sleep(seconds)`` records
    the requested delay and advances the clock by exactly that amount, so time
    moves only when the crawler chooses to wait (or when a fetch simulates a
    response duration). The recorded ``sleeps`` are exactly the delays the
    crawler enforced between requests.
    """

    def __init__(self) -> None:
        self._t = datetime(2024, 1, 1, tzinfo=timezone.utc)
        self.sleeps: list[float] = []

    def now(self) -> datetime:
        return self._t

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.advance(seconds)

    def advance(self, seconds: float) -> None:
        self._t = self._t + timedelta(seconds=seconds)


class TimedFetcher:
    """In-memory fetcher advancing the shared clock by a fixed response time.

    Every fetch advances the fake clock by ``duration_s`` (default 0 s), so the
    crawler observes a realistic elapsed duration without any real waiting. Kept
    below the degradation threshold so pacing stays at the floor (no doubling).
    """

    def __init__(
        self, clock: FakeClock, pages: dict[str, str], duration_s: float = 0.0
    ) -> None:
        self._clock = clock
        self._pages = pages
        self._duration_s = duration_s
        self.requested: list[str] = []

    def fetch(self, url: str) -> FetchResponse:
        self.requested.append(url)
        self._clock.advance(self._duration_s)
        html = self._pages.get(url, "")
        status = 200 if url in self._pages else 404
        return FetchResponse(url=url, final_url=url, status_code=status, html=html)


def _allow_all_gate() -> RobotsGate:
    """A robots gate whose ``robots.txt`` is empty, so everything is allowed."""
    return RobotsGate(lambda _robots_url: "")


def _page(links: list[str] = ()) -> str:
    anchors = "".join(f'<a href="{href}">x</a>' for href in links)
    return f"<html><head><title>T</title></head><body>{anchors}</body></html>"


def _chain(n: int) -> dict[str, str]:
    """A chain of ``n`` same-host pages, each linking to the next.

    The start page links to ``/p0``, ``/p0`` links to ``/p1``, and so on, so a
    breadth-first crawl retrieves the pages one after another — all on the same
    host, exercising the per-host pacing floor between every consecutive pair.
    """
    urls = [f"{BASE}/p{i}" for i in range(n)]
    html = {BASE: _page(links=[urls[0]] if urls else [])}
    for i, url in enumerate(urls):
        nxt = urls[i + 1] if i + 1 < len(urls) else None
        html[url] = _page(links=[nxt] if nxt else [])
    return html


# Fast responses keep every observed duration well under the degradation
# threshold, so the enforced delay is never doubled and sits exactly at the
# configured floor.
_FAST_DURATION_S = 0.0
assert _FAST_DURATION_S * 1000.0 <= DEGRADATION_THRESHOLD_MS


@settings(max_examples=200)
@given(
    # Number of extra same-host pages beyond the start page (0..12): varies the
    # length of the request chain, and thus the number of enforced delays.
    extra_pages=st.integers(min_value=0, max_value=12),
    # A varied configured floor in the required range.
    rate_limit_ms=st.integers(min_value=100, max_value=3000),
)
def test_consecutive_same_host_delays_never_below_floor(
    extra_pages: int, rate_limit_ms: int
) -> None:
    """Every enforced inter-request delay is >= the configured floor.

    **Validates: Requirements 1.9, 1.10**
    """
    clock = FakeClock()
    fetcher = TimedFetcher(clock, _chain(extra_pages), duration_s=_FAST_DURATION_S)
    crawler = Crawler(
        fetcher,
        robots_gate=_allow_all_gate(),
        clock=clock.now,
        sleep=clock.sleep,
        rate_limit_ms=rate_limit_ms,
    )

    pages = crawler.crawl_site(BASE, 10000)

    floor_s = rate_limit_ms / 1000.0

    # The crawl retrieved the start page plus every chained page, all same-host.
    assert len(pages) == extra_pages + 1

    # The first request to a host is never delayed, so N retrieved same-host
    # pages produce exactly N - 1 enforced delays (Req 1.10).
    assert len(clock.sleeps) == len(pages) - 1

    # The core invariant: the enforced delay between consecutive same-host
    # requests is never reduced below the configured floor (Req 1.9, 1.10).
    assert all(delay >= floor_s for delay in clock.sleeps)


@settings(max_examples=200)
@given(rate_limit_ms=st.integers(min_value=100, max_value=3000))
def test_first_request_to_a_host_is_never_delayed(rate_limit_ms: int) -> None:
    """A lone same-host request incurs no pacing delay for any floor.

    **Validates: Requirements 1.9, 1.10**
    """
    clock = FakeClock()
    fetcher = TimedFetcher(clock, {BASE: _page()}, duration_s=_FAST_DURATION_S)
    crawler = Crawler(
        fetcher,
        robots_gate=_allow_all_gate(),
        clock=clock.now,
        sleep=clock.sleep,
        rate_limit_ms=rate_limit_ms,
    )

    pages = crawler.crawl_site(BASE, 10000)

    # One page retrieved -> no inter-request delay at all.
    assert len(pages) == 1
    assert clock.sleeps == []
