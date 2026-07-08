"""Property 3 — Invalid crawl requests retrieve nothing.

Feature: website-orchestrator-milestone-0, Property 3: Invalid crawl requests
retrieve nothing

Validates: Requirements 1.5

Requirement 1.5: IF ``start_url`` is malformed OR ``max_pages`` is outside the
range 1 to 10000, THEN THE Crawler SHALL reject the invocation with a typed
error and SHALL NOT retrieve any page.

This property drives :meth:`crawler.crawler.Crawler.crawl_site` with invalid
inputs drawn from two disjoint families:

* **(a) Malformed ``start_url`` with a valid ``max_pages``.** The start URL is
  drawn from the ways a URL can be malformed — empty/whitespace-only, missing
  scheme, a non-http(s) scheme (``ftp``, ``mailto``, ``tel``, ``file`` ...), a
  missing host, and non-string values (``None``, ints, floats, bools, lists) —
  while ``max_pages`` is a perfectly valid integer in ``[1, 10000]``. The only
  reason to reject is the malformed URL.
* **(b) Valid ``start_url`` with an out-of-range ``max_pages``.** The start URL
  is a well-formed http/https URL, while ``max_pages`` is out of the inclusive
  range ``[1, 10000]`` — ``<= 0``, ``> 10000``, or a non-integer (``bool``,
  ``float``, ``str``, ``None``). The only reason to reject is the bad count.

For every generated invalid request the crawl must raise
:class:`~core.exceptions.InvalidCrawlRequest` **and** retrieve nothing. "Retrieve
nothing" is asserted directly against a recording fetcher spy: its ``.requested``
list captures every URL the crawler would fetch, and it must stay empty. Because
validation happens strictly before any retrieval, the spy is never called (and
no live site is ever contacted, Req 2.5).
"""

from __future__ import annotations

from urllib.parse import urlsplit

import pytest
from hypothesis import example, given, settings
from hypothesis import strategies as st

from core.exceptions import InvalidCrawlRequest

from crawler import Crawler, FetchResponse, RobotsGate


# --- Recording fetcher spy ----------------------------------------------------


class RecordingFetcher:
    """An in-memory :class:`crawler.fetcher.Fetcher` that records every request.

    ``requested`` captures the URL of every :meth:`fetch` call, so a test can
    assert that *no* retrieval happened by checking it stayed empty (Req 1.5).
    It never contacts a live site (Req 2.5).
    """

    def __init__(self) -> None:
        self.requested: list[str] = []

    def fetch(self, url: str) -> FetchResponse:
        self.requested.append(url)
        return FetchResponse(url=url, final_url=url, status_code=200, html="")


def _allow_all_gate() -> RobotsGate:
    """A network-free robots gate whose empty robots.txt allows every URL."""
    return RobotsGate(lambda _robots_url: "")


def _crawler(fetcher: RecordingFetcher) -> Crawler:
    """A Crawler wired to the recording spy and an allow-all robots gate.

    The link prober is left at its default: ``crawl_site`` never probes links,
    and it is never constructed lazily unless used, so no network is touched.
    """
    return Crawler(fetcher, robots_gate=_allow_all_gate())


# --- Spec-level validity oracle ----------------------------------------------


def _is_valid_http_url(value: object) -> bool:
    """Return ``True`` iff ``value`` is a well-formed http/https URL with a host.

    This mirrors the acceptance criterion's notion of a *well-formed* start URL
    (a syntactically valid ``http``/``https`` URL with a host), independent of
    the crawler's private helper. It is used only to keep the generated families
    honest: family (a) discards any string that is accidentally valid, and
    family (b) keeps only URLs that are genuinely valid.
    """
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        parts = urlsplit(value.strip())
    except ValueError:
        return False
    return parts.scheme.lower() in {"http", "https"} and bool(parts.hostname)


# --- Strategies: family (a) malformed start_url ------------------------------

# Empty and whitespace-only strings.
_blank_urls = st.text(alphabet=" \t\n\r\f\v", max_size=6)

# Host-like text with no scheme at all: "example.com", "example.com/path".
_no_scheme_urls = st.builds(
    lambda host, path: f"{host}{path}",
    st.from_regex(r"[a-z]{1,12}\.[a-z]{2,4}", fullmatch=True),
    st.sampled_from(["", "/", "/a", "/a/b", "/index.html", ":8080"]),
)

# A syntactically fine URL but with a scheme the crawler will not retrieve.
_bad_scheme_urls = st.builds(
    lambda scheme, host: f"{scheme}://{host}",
    st.sampled_from(
        ["ftp", "mailto", "tel", "file", "data", "ws", "wss", "gopher", "sftp"]
    ),
    st.from_regex(r"[a-z]{1,12}\.[a-z]{2,4}", fullmatch=True),
)

# mailto:/tel: style opaque URLs (scheme present, no host).
_opaque_urls = st.builds(
    lambda scheme, rest: f"{scheme}:{rest}",
    st.sampled_from(["mailto", "tel", "javascript", "data"]),
    st.sampled_from(["user@example.com", "+15551234", "alert(1)", "text/plain,x"]),
)

# http(s) URLs with no host component.
_no_host_urls = st.sampled_from(
    ["http://", "https://", "http:///path", "https:///", "http://:8080", "https://#f"]
)

# Non-string inputs — always malformed regardless of value.
_non_string = st.one_of(
    st.none(),
    st.integers(),
    st.floats(allow_nan=True, allow_infinity=True),
    st.booleans(),
    st.lists(st.integers(), max_size=3),
    st.tuples(st.integers()),
    st.binary(max_size=8),
)

_malformed_start_url = st.one_of(
    _blank_urls,
    _no_scheme_urls,
    _bad_scheme_urls,
    _opaque_urls,
    _no_host_urls,
    _non_string,
).filter(lambda v: not _is_valid_http_url(v))

# A valid page count so family (a) is rejected *only* for the malformed URL.
_valid_max_pages = st.integers(min_value=1, max_value=10000)


# --- Strategies: family (b) out-of-range / non-int max_pages -----------------

_valid_start_url = st.builds(
    lambda scheme, host, path: f"{scheme}://{host}{path}",
    st.sampled_from(["http", "https"]),
    st.from_regex(r"[a-z]{1,12}\.[a-z]{2,4}", fullmatch=True),
    st.sampled_from(["", "/", "/a", "/a/b", "/index.html", "/p?q=1"]),
).filter(_is_valid_http_url)

_too_small = st.integers(max_value=0)
_too_large = st.integers(min_value=10001)
_non_int_max_pages = st.one_of(
    st.booleans(),  # bool is an int subclass but must be rejected
    st.floats(allow_nan=False, allow_infinity=False),
    st.text(max_size=5),
    st.none(),
)
_invalid_max_pages = st.one_of(_too_small, _too_large, _non_int_max_pages)


# --- Property 3 ---------------------------------------------------------------


@settings(max_examples=100)
@given(start_url=_malformed_start_url, max_pages=_valid_max_pages)
@example(start_url="", max_pages=10)
@example(start_url="   ", max_pages=10)
@example(start_url="example.com", max_pages=10)
@example(start_url="ftp://example.com", max_pages=10)
@example(start_url="mailto:user@example.com", max_pages=10)
@example(start_url="http://", max_pages=10)
@example(start_url=None, max_pages=10)
@example(start_url=123, max_pages=10)
def test_property_03_malformed_start_url_retrieves_nothing(
    start_url: object, max_pages: int
) -> None:
    """A malformed ``start_url`` raises and the fetcher is never called (Req 1.5).

    Feature: website-orchestrator-milestone-0, Property 3: Invalid crawl requests
    retrieve nothing

    Validates: Requirements 1.5
    """
    fetcher = RecordingFetcher()
    crawler = _crawler(fetcher)

    with pytest.raises(InvalidCrawlRequest):
        crawler.crawl_site(start_url, max_pages)

    # Retrieved nothing: the recording spy captured zero requests.
    assert fetcher.requested == []


@settings(max_examples=100)
@given(start_url=_valid_start_url, max_pages=_invalid_max_pages)
@example(start_url="https://example.com", max_pages=0)
@example(start_url="https://example.com", max_pages=-1)
@example(start_url="https://example.com", max_pages=10001)
@example(start_url="https://example.com", max_pages=True)
@example(start_url="https://example.com", max_pages=1.5)
@example(start_url="https://example.com", max_pages="5")
def test_property_03_out_of_range_max_pages_retrieves_nothing(
    start_url: str, max_pages: object
) -> None:
    """An out-of-range/non-int ``max_pages`` raises and nothing is fetched (Req 1.5).

    Feature: website-orchestrator-milestone-0, Property 3: Invalid crawl requests
    retrieve nothing

    Validates: Requirements 1.5
    """
    fetcher = RecordingFetcher()
    crawler = _crawler(fetcher)

    with pytest.raises(InvalidCrawlRequest):
        crawler.crawl_site(start_url, max_pages)

    # Retrieved nothing: the recording spy captured zero requests.
    assert fetcher.requested == []
