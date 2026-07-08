"""Property 9 — check_link_status reports observed status or unreachable.

Feature: website-orchestrator-milestone-0, Property 9: check_link_status reports
observed status or unreachable.

**Validates: Requirements 2.3, 2.4**

:meth:`~crawler.crawler.Crawler.check_link_status` observes a single link's HTTP
status through an injectable :class:`~crawler.fetcher.LinkProber`. Two universal
behaviors must hold for *any* input:

* **Observed status (Req 2.3).** For any observed integer HTTP status the prober
  returns, ``check_link_status`` returns a :class:`~core.types.LinkStatus`
  carrying that exact ``status_code``, ``reachable=True``, and the requested
  ``url`` — any HTTP status counts as an observation because a server responded.
* **Unreachable on failure (Req 2.4).** For any exception the prober raises
  (timeout, network failure, or a generic error), ``check_link_status`` returns
  a :class:`~core.types.LinkStatus` with ``status_code=None`` and
  ``reachable=False`` and does NOT let the exception propagate.

Both families are generated and driven through an injected in-memory prober, so
no live site is ever contacted (Req 2.5).
"""

from __future__ import annotations

import httpx
from hypothesis import given, settings
from hypothesis import strategies as st

from crawler import Crawler, RobotsGate


def _crawler(link_prober) -> Crawler:
    """Build a Crawler with the injected link prober and an allow-all gate."""
    return Crawler(robots_gate=RobotsGate(lambda _robots_url: ""), link_prober=link_prober)


# --- Generators ---------------------------------------------------------------

# Any URL string the caller might probe. A small alphabet keeps examples compact
# while still varying the URL that must be echoed back on the result.
_urls = st.builds(
    lambda host, path: f"https://{host}.example.com/{path}",
    host=st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789-", min_size=1, max_size=12),
    path=st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789/-_", max_size=24),
)

# Any observed HTTP status across the full 100..599 range (Req 2.3): a server
# responded with this code, so the link is reachable regardless of the value.
_observed_status = st.integers(min_value=100, max_value=599)

# The families of failures a prober can raise (Req 2.4): a timeout, a network
# failure (connect/read), or a generic error. Built lazily so a fresh exception
# instance is raised on each probe.
_exception_factories = st.sampled_from(
    [
        lambda: httpx.TimeoutException("timed out"),
        lambda: httpx.ConnectError("connection refused"),
        lambda: httpx.ReadError("read failed"),
        lambda: httpx.HTTPError("generic http error"),
        lambda: RuntimeError("boom"),
        lambda: OSError("network is unreachable"),
    ]
)


# --- Property 9 ---------------------------------------------------------------


@settings(max_examples=200)
@given(url=_urls, status=_observed_status)
def test_observed_status_is_reported_reachable(url: str, status: int) -> None:
    """Any observed status yields that status_code, reachable, and the url.

    **Validates: Requirements 2.3**
    """
    seen: list[str] = []

    def prober(probe_url: str) -> int:
        seen.append(probe_url)
        return status

    result = _crawler(prober).check_link_status(url)

    assert result.url == url
    assert result.status_code == status
    assert result.reachable is True
    # The prober was invoked exactly once with the requested URL.
    assert seen == [url]


@settings(max_examples=200)
@given(url=_urls, make_exc=_exception_factories)
def test_prober_failure_yields_unreachable_without_raising(url: str, make_exc) -> None:
    """Any raised failure yields status_code=None, reachable=False, no raise.

    **Validates: Requirements 2.4**
    """

    def prober(_probe_url: str) -> int:
        raise make_exc()

    # Must not propagate: calling check_link_status returns normally.
    result = _crawler(prober).check_link_status(url)

    assert result.url == url
    assert result.status_code is None
    assert result.reachable is False
