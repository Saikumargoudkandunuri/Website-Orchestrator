"""Unit tests for link-status probing (task 5.5, Req 2.3, 2.4, 2.5).

:meth:`~crawler.crawler.Crawler.check_link_status` observes a single link's HTTP
status through an injectable :class:`~crawler.fetcher.LinkProber`. These tests
inject an in-memory prober — one that returns a canned status or raises a
simulated timeout/network failure — so every case is exercised deterministically
without ever contacting the network (Req 2.5).
"""

from __future__ import annotations

import httpx
import pytest

from core.constants import LINK_TIMEOUT_S

from crawler import Crawler, RobotsGate


def _allow_all_gate() -> RobotsGate:
    """A network-free robots gate whose empty robots.txt allows every URL."""
    return RobotsGate(lambda _robots_url: "")


def _crawler(link_prober) -> Crawler:
    """Build a Crawler with the injected link prober and an allow-all gate."""
    return Crawler(robots_gate=_allow_all_gate(), link_prober=link_prober)


# --- Observed status is returned, reachable True (Req 2.3) -------------------


@pytest.mark.parametrize("status", [200, 201, 301, 400, 404, 410, 500, 503])
def test_observed_status_is_returned_and_reachable(status):
    url = "https://example.com/page"
    # The prober responded (any HTTP status is an observation) -> reachable.
    result = _crawler(lambda _url: status).check_link_status(url)

    assert result.url == url
    assert result.status_code == status
    assert result.reachable is True


def test_probe_is_called_with_the_requested_url():
    seen: list[str] = []

    def prober(url: str) -> int:
        seen.append(url)
        return 200

    url = "https://example.com/some/path"
    _crawler(prober).check_link_status(url)

    assert seen == [url]


# --- Timeout / network failure -> unreachable without raising (Req 2.4) ------


def test_timeout_returns_unreachable_without_raising():
    def prober(_url: str) -> int:
        raise httpx.TimeoutException("timed out")

    result = _crawler(prober).check_link_status("https://example.com/slow")

    assert result.status_code is None
    assert result.reachable is False


def test_network_failure_returns_unreachable_without_raising():
    def prober(_url: str) -> int:
        raise httpx.ConnectError("connection refused")

    result = _crawler(prober).check_link_status("https://example.com/down")

    assert result.status_code is None
    assert result.reachable is False


def test_generic_exception_is_contained_and_reported_unreachable():
    def prober(_url: str) -> int:
        raise RuntimeError("boom")

    result = _crawler(prober).check_link_status("https://example.com/broken")

    assert result.status_code is None
    assert result.reachable is False


# --- Default timeout / DI wiring (Req 2.3, 2.5) ------------------------------


def test_default_link_timeout_is_ten_seconds():
    # The documented default probe timeout is LINK_TIMEOUT_S (Req 2.3).
    assert LINK_TIMEOUT_S == 10


def test_default_prober_is_constructed_without_touching_the_network():
    # Constructing a Crawler with no injected prober must not open any network
    # resource (the httpx client is created lazily on first probe).
    crawler = Crawler(robots_gate=_allow_all_gate())
    assert crawler is not None
