"""Property test for per-host degradation backoff (task 5.11).

Feature: website-orchestrator-milestone-0, Property 6: Delay doubles under
observed degradation.

**Validates: Requirements 1.11**

Property 6 states that for any per-host request sequence, whenever the observed
response time for a page exceeds the configured degradation threshold, the delay
the Crawler enforces before the *next* request to that host is at least double
the configured Rate_Limit (Req 1.11). Conversely, once a response recovers to at
or below the threshold, the next delay drops back to the Rate_Limit floor (never
below it, Req 1.9/1.10).

The fixture is a linear chain of same-host pages ``p0 -> p1 -> ... -> p(n-1)``.
Retrieval visits them in order, so the crawl enforces exactly one inter-request
delay after each page except the last: ``sleeps[k]`` is the delay enforced
immediately *after* fetching page ``k`` and *before* fetching page ``k+1``.
Whether ``sleeps[k]`` is doubled therefore depends solely on whether page ``k``'s
observed response time exceeded the degradation threshold.

All timing is driven by an injected fake clock plus a recording sleep, and a
:class:`TimedFetcher` advances that clock by a per-URL response duration to
simulate slow responses. Because the fake clock only moves when the crawler
sleeps or when a fetch simulates a duration, the recorded sleeps are exactly the
delays the crawler enforced — no real waiting and no network (Req 2.5).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from hypothesis import given
from hypothesis import strategies as st

from crawler import Crawler, FetchResponse, RobotsGate

DOMAIN = "https://example.com"

# Keep sizes modest so 100+ examples stay fast.
MAX_CHAIN_PAGES = 10


class FakeClock:
    """Deterministic, injectable clock plus a recording sleep.

    ``now()`` returns the current simulated UTC time. ``sleep(seconds)`` records
    the requested delay and advances the clock by exactly that amount, so time
    only moves when the crawler chooses to wait (or when a fetch simulates a
    response duration via :meth:`advance`).
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
    """In-memory fetcher that simulates a per-URL response duration.

    On each fetch it advances the shared fake clock by the URL's configured
    response time (default 0 s), so the crawler observes a realistic elapsed
    duration without any real waiting, and never contacts a live site (Req 2.5).
    """

    def __init__(
        self,
        clock: FakeClock,
        pages: dict[str, str],
        durations_s: dict[str, float] | None = None,
        default_duration_s: float = 0.0,
    ) -> None:
        self._clock = clock
        self._pages = pages
        self._durations = durations_s or {}
        self._default_duration_s = default_duration_s
        self.requested: list[str] = []

    def fetch(self, url: str) -> FetchResponse:
        self.requested.append(url)
        self._clock.advance(self._durations.get(url, self._default_duration_s))
        html = self._pages.get(url, "")
        status = 200 if url in self._pages else 404
        return FetchResponse(url=url, final_url=url, status_code=status, html=html)


def _allow_all_gate() -> RobotsGate:
    """A network-free :class:`RobotsGate` whose empty robots.txt allows every URL."""
    return RobotsGate(lambda _robots_url: "")


def _url(index: int) -> str:
    """Stable, already-normalized URL for page ``index`` on the fixture domain."""
    return DOMAIN if index == 0 else f"{DOMAIN}/p{index}"


def _linear_chain(n: int) -> dict[str, str]:
    """HTML for a linear chain ``p0 -> p1 -> ... -> p(n-1)`` on one host.

    Each page links only to its successor, so a breadth-first crawl retrieves
    the pages strictly in index order, giving one inter-request delay after each
    page except the last.
    """
    html: dict[str, str] = {}
    for i in range(n):
        successor = f'<a href="{_url(i + 1)}">next</a>' if i + 1 < n else ""
        html[_url(i)] = (
            f"<html><head><title>T{i}</title></head>"
            f"<body>{successor}</body></html>"
        )
    return html


@st.composite
def _degradation_scenario(draw: st.DrawFn) -> dict:
    """Generate a same-host chain with varied pacing config and slow responses.

    Produces:
      * ``rate_limit_ms`` — a positive Rate_Limit floor (so a delay is always
        enforced between same-host requests).
      * ``threshold_ms`` — the degradation threshold to compare durations to.
      * a per-page ``is_slow`` flag; a slow page's simulated response time is
        strictly greater than ``threshold_ms`` (and well under the 30 s
        per-request timeout so it is never abandoned), while a fast page
        responds instantly.
    """
    n = draw(st.integers(min_value=2, max_value=MAX_CHAIN_PAGES))
    rate_limit_ms = draw(st.integers(min_value=1, max_value=3000))
    threshold_ms = draw(st.integers(min_value=500, max_value=5000))
    is_slow = draw(st.lists(st.booleans(), min_size=n, max_size=n))
    # Slow overshoot kept small so total duration stays far below the 30 s
    # per-request timeout (which would otherwise abandon the request).
    slow_deltas_ms = draw(
        st.lists(st.integers(min_value=1, max_value=3000), min_size=n, max_size=n)
    )
    return {
        "n": n,
        "rate_limit_ms": rate_limit_ms,
        "threshold_ms": threshold_ms,
        "is_slow": is_slow,
        "slow_deltas_ms": slow_deltas_ms,
    }


@pytest.mark.property
@given(_degradation_scenario())
def test_delay_doubles_under_observed_degradation(scenario: dict) -> None:
    """After a slow response the next same-host delay is >= 2x the Rate_Limit.

    Feature: website-orchestrator-milestone-0, Property 6: Delay doubles under
    observed degradation. **Validates: Requirements 1.11**

    For every page ``k`` that has a successor, the delay ``sleeps[k]`` enforced
    before fetching page ``k+1`` is:

    * at least double the configured Rate_Limit when page ``k``'s observed
      response time exceeded the degradation threshold (Req 1.11); and
    * exactly the Rate_Limit floor when it did not (recovery to the floor,
      never below it — Req 1.9/1.10).
    """
    n = scenario["n"]
    rate_limit_ms = scenario["rate_limit_ms"]
    threshold_ms = scenario["threshold_ms"]
    is_slow = scenario["is_slow"]
    slow_deltas_ms = scenario["slow_deltas_ms"]

    # A slow page responds just past the threshold; a fast page responds
    # instantly. Durations are in seconds for the TimedFetcher.
    durations_s: dict[str, float] = {}
    for i in range(n):
        if is_slow[i]:
            durations_s[_url(i)] = (threshold_ms + slow_deltas_ms[i]) / 1000.0

    clock = FakeClock()
    fetcher = TimedFetcher(clock, _linear_chain(n), durations_s=durations_s)
    crawler = Crawler(
        fetcher,
        robots_gate=_allow_all_gate(),
        clock=clock.now,
        sleep=clock.sleep,
        rate_limit_ms=rate_limit_ms,
        degradation_threshold_ms=threshold_ms,
    )

    pages = crawler.crawl_site(_url(0), n)

    # The whole chain is retrieved in order, so there is exactly one enforced
    # delay after each page except the last.
    assert len(pages) == n
    assert len(clock.sleeps) == n - 1

    floor_s = rate_limit_ms / 1000.0
    for k in range(n - 1):
        delay = clock.sleeps[k]
        # A delay is never reduced below the configured Rate_Limit floor
        # (Req 1.9/1.10).
        assert delay >= floor_s - 1e-9
        if is_slow[k]:
            # Page k's response exceeded the degradation threshold, so the next
            # same-host delay is at least doubled (Req 1.11).
            assert delay >= 2.0 * floor_s - 1e-9
        else:
            # A response at/under the threshold keeps the next delay at the
            # floor — it recovers rather than staying doubled.
            assert delay == pytest.approx(floor_s)
