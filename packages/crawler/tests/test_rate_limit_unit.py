"""Unit tests for per-host pacing: rate-limit floor, degradation backoff, and
the per-request timeout (task 5.3, Req 1.9-1.12).

All timing is driven by an injected fake clock and a recording sleep, so these
tests are fully deterministic and never wait on or contact the network
(Req 2.5). The fake clock only advances when the code sleeps or when the fake
fetcher deliberately simulates a response duration, so the enforced delays are
exactly the sleep values recorded here.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from core.constants import (
    DEFAULT_RATE_LIMIT_MS,
    DEGRADATION_THRESHOLD_MS,
    REQUEST_TIMEOUT_S,
)

from crawler import Crawler, FetchResponse, RobotsGate


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
    duration without any real waiting.
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
    return RobotsGate(lambda _robots_url: "")


def _page(links: list[str] = ()) -> str:
    anchors = "".join(f'<a href="{href}">x</a>' for href in links)
    return f"<html><head><title>T</title></head><body>{anchors}</body></html>"


def _chain(base: str, n: int) -> dict[str, str]:
    """A chain of ``n`` same-host pages, each linking to the next."""
    urls = [f"{base}/p{i}" for i in range(n)]
    html = {base: _page(links=[urls[0]])}
    for i, url in enumerate(urls):
        nxt = urls[i + 1] if i + 1 < len(urls) else None
        html[url] = _page(links=[nxt] if nxt else [])
    return html


# --- Rate-limit floor (Req 1.9, 1.10) ----------------------------------------


def test_consecutive_same_host_delays_are_at_least_the_floor():
    clock = FakeClock()
    base = "https://example.com"
    fetcher = TimedFetcher(clock, _chain(base, 4))  # fast responses (0 s)
    crawler = Crawler(
        fetcher,
        robots_gate=_allow_all_gate(),
        clock=clock.now,
        sleep=clock.sleep,
    )

    pages = crawler.crawl_site(base, 5)

    # 5 same-host pages retrieved -> 4 inter-request delays enforced.
    assert len(pages) == 5
    assert len(clock.sleeps) == 4
    floor_s = DEFAULT_RATE_LIMIT_MS / 1000.0
    # Every enforced delay honors the floor and is never reduced below it.
    assert all(delay >= floor_s for delay in clock.sleeps)
    # Fast responses stay exactly at the floor (never doubled).
    assert all(delay == pytest.approx(floor_s) for delay in clock.sleeps)


def test_first_request_to_a_host_is_not_delayed():
    clock = FakeClock()
    base = "https://example.com"
    fetcher = TimedFetcher(clock, {base: _page()})
    crawler = Crawler(
        fetcher,
        robots_gate=_allow_all_gate(),
        clock=clock.now,
        sleep=clock.sleep,
    )

    crawler.crawl_site(base, 5)

    # Only one page -> no inter-request delay at all.
    assert clock.sleeps == []


def test_configured_floor_is_honored():
    clock = FakeClock()
    base = "https://example.com"
    fetcher = TimedFetcher(clock, _chain(base, 2))
    crawler = Crawler(
        fetcher,
        robots_gate=_allow_all_gate(),
        clock=clock.now,
        sleep=clock.sleep,
        rate_limit_ms=500,
    )

    crawler.crawl_site(base, 3)

    assert clock.sleeps  # at least one delay enforced
    assert all(delay >= 0.5 for delay in clock.sleeps)


# --- Degradation backoff (Req 1.11) ------------------------------------------


def test_delay_doubles_after_response_exceeds_degradation_threshold():
    clock = FakeClock()
    base = "https://example.com"
    slow_s = (DEGRADATION_THRESHOLD_MS + 1000) / 1000.0  # > threshold
    # The start page responds slowly; the crawler must double the delay before
    # the next same-host request.
    fetcher = TimedFetcher(
        clock,
        _chain(base, 2),
        durations_s={base: slow_s},
    )
    crawler = Crawler(
        fetcher,
        robots_gate=_allow_all_gate(),
        clock=clock.now,
        sleep=clock.sleep,
    )

    crawler.crawl_site(base, 3)

    floor_s = DEFAULT_RATE_LIMIT_MS / 1000.0
    assert clock.sleeps, "expected at least one enforced delay"
    # The delay immediately after the slow response is at least double the floor.
    assert clock.sleeps[0] >= 2.0 * floor_s


def test_delay_returns_to_floor_after_response_recovers():
    clock = FakeClock()
    base = "https://example.com"
    slow_s = (DEGRADATION_THRESHOLD_MS + 1000) / 1000.0
    # First page slow (triggers doubling), remaining pages fast (recover).
    fetcher = TimedFetcher(
        clock,
        _chain(base, 3),
        durations_s={base: slow_s},
        default_duration_s=0.0,
    )
    crawler = Crawler(
        fetcher,
        robots_gate=_allow_all_gate(),
        clock=clock.now,
        sleep=clock.sleep,
    )

    crawler.crawl_site(base, 4)

    floor_s = DEFAULT_RATE_LIMIT_MS / 1000.0
    assert len(clock.sleeps) >= 2
    # After the slow response the delay is doubled ...
    assert clock.sleeps[0] >= 2.0 * floor_s
    # ... and once responses recover it drops back to the floor.
    assert clock.sleeps[1] == pytest.approx(floor_s)


# --- Per-request timeout (Req 1.12) ------------------------------------------


def test_request_exceeding_timeout_is_abandoned():
    clock = FakeClock()
    base = "https://example.com"
    over_timeout_s = REQUEST_TIMEOUT_S + 5
    # The start page "hangs" past the per-request timeout; it must be abandoned
    # (skipped) rather than returned or crashing.
    fetcher = TimedFetcher(
        clock,
        {base: _page(), f"{base}/ok": _page()},
        durations_s={base: over_timeout_s},
    )
    crawler = Crawler(
        fetcher,
        robots_gate=_allow_all_gate(),
        clock=clock.now,
        sleep=clock.sleep,
    )

    pages = crawler.crawl_site(base, 5)

    retrieved = {p.url for p in pages}
    # The timed-out start URL yields no page, and since links are discovered
    # from its (abandoned) body, nothing else is retrieved either.
    assert base not in retrieved
    assert pages == []


def test_fetcher_error_is_skipped_not_fatal():
    clock = FakeClock()
    base = "https://example.com"

    class BoomFetcher:
        def __init__(self) -> None:
            self.requested: list[str] = []

        def fetch(self, url: str) -> FetchResponse:
            self.requested.append(url)
            raise ConnectionError("boom")

    crawler = Crawler(
        BoomFetcher(),
        robots_gate=_allow_all_gate(),
        clock=clock.now,
        sleep=clock.sleep,
    )

    pages = crawler.crawl_site(base, 5)

    # A raising fetch is skipped, not propagated.
    assert pages == []


def test_request_within_timeout_is_kept():
    clock = FakeClock()
    base = "https://example.com"
    under_timeout_s = REQUEST_TIMEOUT_S - 1
    fetcher = TimedFetcher(
        clock,
        {base: _page()},
        durations_s={base: under_timeout_s},
    )
    crawler = Crawler(
        fetcher,
        robots_gate=_allow_all_gate(),
        clock=clock.now,
        sleep=clock.sleep,
    )

    pages = crawler.crawl_site(base, 5)

    assert len(pages) == 1
    assert pages[0].url == base
