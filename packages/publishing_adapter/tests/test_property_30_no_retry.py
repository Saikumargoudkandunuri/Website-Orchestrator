"""Property 30 — No retry: a failed request is attempted exactly once.

Feature: website-orchestrator-milestone-0, Property 30: No retry — a failed
request is attempted exactly once.

**Validates: Requirements 7.6**

The Publishing_Adapter performs **exactly one** HTTP attempt per public call and
contains no retry logic — the caller owns retries (Req 7.6). This module drives
that guarantee with property-based tests: for an arbitrary failing HTTP status,
an arbitrary transport-level exception (timeout / connect / read / network /
protocol error), *and* the success path, invoking any of the five client
methods results in **exactly one** request reaching the transport. The request
count is captured network-free via an injected ``httpx.MockTransport`` wrapped in
a recorder that increments *before* delegating to the handler, so an attempt is
counted even when the handler raises. Alongside the single-attempt assertion we
confirm the outcome contract: each failing status maps to the appropriate typed
``WP*`` error, transport failures wrap to :class:`WPClientError`, and a success
returns normally.
"""

from __future__ import annotations

import httpx
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import SecretStr

from core.exceptions import (
    WPAuthError,
    WPClientError,
    WPNotFoundError,
    WPRateLimitError,
)
from publishing_adapter import WordPressClient

BASE_URL = "https://example.com"
USERNAME = "editor"
APP_PASSWORD = SecretStr("abcd efgh ijkl mnop")


class _Recorder:
    """Counts every request an injected transport handles.

    The count is incremented *before* the handler runs, so a raised transport
    exception still registers exactly one attempt — which is precisely what the
    no-retry property must observe.
    """

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []


def _make_client(handler, recorder: _Recorder) -> WordPressClient:
    """Build a network-free client whose transport records then delegates."""

    def _wrapped(request: httpx.Request) -> httpx.Response:
        recorder.requests.append(request)
        return handler(request)

    transport = httpx.MockTransport(_wrapped)
    http_client = httpx.Client(transport=transport, base_url=BASE_URL)
    return WordPressClient(BASE_URL, USERNAME, APP_PASSWORD, client=http_client)


# --- Invocation dispatch -----------------------------------------------------

_METHOD_KINDS = (
    "list_pages",
    "get_page",
    "update_page_content",
    "get_media",
    "update_media_alt_text",
)


def _invoke(client: WordPressClient, kind: str, ident: int, text: str):
    """Invoke the chosen client method, exercising every public entry point."""
    if kind == "list_pages":
        return client.list_pages()
    if kind == "get_page":
        return client.get_page(ident)
    if kind == "update_page_content":
        return client.update_page_content(ident, text)
    if kind == "get_media":
        return client.get_media(ident)
    return client.update_media_alt_text(ident, text)


# --- Strategies --------------------------------------------------------------

_ids = st.integers(min_value=1, max_value=2**31 - 1)
_texts = st.text(max_size=64)
_method_kind = st.sampled_from(_METHOD_KINDS)

# Failing statuses: the specifically-classified ones plus arbitrary other
# 4xx/5xx codes (Req 7.1-7.4).
_specific_failures = st.sampled_from([401, 403, 404, 429, 500, 502, 503])
_other_4xx = st.integers(min_value=400, max_value=499).filter(
    lambda s: s not in (401, 403, 404, 429)
)
_other_5xx = st.integers(min_value=500, max_value=599)
_failing_status = st.one_of(_specific_failures, _other_4xx, _other_5xx)

# Transport-level exception families — all must wrap to WPClientError (Req 7.8).
_TRANSPORT_EXC_KINDS = (
    "timeout",
    "connect_timeout",
    "read_timeout",
    "pool_timeout",
    "connect_error",
    "read_error",
    "network_error",
    "protocol_error",
)
_transport_exc_kind = st.sampled_from(_TRANSPORT_EXC_KINDS)


def _raise_transport_exc(kind: str, request: httpx.Request):
    """Raise the selected httpx transport-level exception."""
    if kind == "timeout":
        raise httpx.TimeoutException("boom", request=request)
    if kind == "connect_timeout":
        raise httpx.ConnectTimeout("boom", request=request)
    if kind == "read_timeout":
        raise httpx.ReadTimeout("boom", request=request)
    if kind == "pool_timeout":
        raise httpx.PoolTimeout("boom", request=request)
    if kind == "connect_error":
        raise httpx.ConnectError("boom", request=request)
    if kind == "read_error":
        raise httpx.ReadError("boom", request=request)
    if kind == "network_error":
        raise httpx.NetworkError("boom", request=request)
    raise httpx.ProtocolError("boom", request=request)


def _expected_status_error(status: int) -> type[Exception]:
    """The single typed error a failing status must map to (Req 7.1-7.4, 7.9)."""
    if status in (401, 403):
        return WPAuthError
    if status == 429:
        return WPRateLimitError
    if status == 404:
        return WPNotFoundError
    return WPClientError


def _success_handler(request: httpx.Request) -> httpx.Response:
    """Return a valid payload shaped for whichever endpoint was hit."""
    path = request.url.path
    if path.endswith("/pages"):
        return httpx.Response(200, json=[])
    if "/media/" in path:
        return httpx.Response(200, json={"id": 1, "alt_text": "ok"})
    return httpx.Response(200, json={"id": 1, "content": {"rendered": "ok"}})


# --- Property 30 -------------------------------------------------------------


@settings(max_examples=150)
@given(kind=_method_kind, ident=_ids, text=_texts, status=_failing_status)
def test_property_30_failing_status_is_attempted_exactly_once(
    kind: str, ident: int, text: str, status: int
) -> None:
    """Any failing HTTP status raises the right typed error after exactly one
    attempt — the adapter never retries (Req 7.6)."""
    rec = _Recorder()
    client = _make_client(lambda req: httpx.Response(status, json={}), rec)

    expected = _expected_status_error(status)
    with pytest.raises(expected):
        _invoke(client, kind, ident, text)

    # Exactly one attempt reached the transport — no retry loop.
    assert len(rec.requests) == 1


@settings(max_examples=150)
@given(kind=_method_kind, ident=_ids, text=_texts, exc_kind=_transport_exc_kind)
def test_property_30_transport_exception_is_attempted_exactly_once(
    kind: str, ident: int, text: str, exc_kind: str
) -> None:
    """Any transport-level failure wraps to WPClientError after exactly one
    attempt — raw httpx errors never escape and no retry occurs (Req 7.6, 7.8)."""
    rec = _Recorder()
    client = _make_client(
        lambda req: _raise_transport_exc(exc_kind, req), rec
    )

    with pytest.raises(WPClientError) as excinfo:
        _invoke(client, kind, ident, text)

    # The raw httpx exception is wrapped, never propagated (Req 7.8, 12.4).
    assert not isinstance(excinfo.value, httpx.HTTPError)
    # Exactly one attempt reached the transport — no retry loop.
    assert len(rec.requests) == 1


@settings(max_examples=100)
@given(kind=_method_kind, ident=_ids, text=_texts)
def test_property_30_success_is_attempted_exactly_once(
    kind: str, ident: int, text: str
) -> None:
    """A successful call also issues exactly one request (baseline: no
    speculative or duplicate attempts on the happy path)."""
    rec = _Recorder()
    client = _make_client(_success_handler, rec)

    _invoke(client, kind, ident, text)

    assert len(rec.requests) == 1
