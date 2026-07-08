"""Property 32 — Every failure is classified as exactly one typed error.

Feature: website-orchestrator-milestone-0, Property 32: Every failure is
classified as exactly one typed error

**Validates: Requirements 7.1, 7.2, 7.3, 7.4, 7.8, 7.9, 12.4**

The Publishing_Adapter turns *every* WordPress failure into exactly one typed
:class:`~core.exceptions.PublishingError` subclass — callers never see a raw
:mod:`httpx` exception (Req 12.4) and never see more than one applicable leaf
type (Req 7.9). The classification rules are:

* HTTP ``401``/``403`` → :class:`WPAuthError` (Req 7.1)
* HTTP ``429`` → :class:`WPRateLimitError` (Req 7.2)
* HTTP ``404`` → :class:`WPNotFoundError` (Req 7.3)
* any other ``4xx``/``5xx`` → :class:`WPClientError` (Req 7.4)
* a request timeout or any other transport/network failure → :class:`WPClientError`
  (Req 7.8)

This module drives those rules with property-based tests over the full failing
status range (400-599) and the whole family of :mod:`httpx` transport
exceptions, exercised through *every* public client method. For each generated
failure it asserts three things:

1. the raised error is an instance of the expected leaf class;
2. it is NOT an instance of the sibling leaf classes it must be mutually
   exclusive with (exactly-one classification, Req 7.9) — noting all four
   share the :class:`PublishingError` base, so the check targets the concrete
   leaf types; and
3. the raised error is a :class:`PublishingError` but NOT a raw
   :class:`httpx.HTTPError` (wrapping, never propagation, Req 12.4).

All requests are network-free via an injected ``httpx.MockTransport``.
"""

from __future__ import annotations

import httpx
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import SecretStr

from core.exceptions import (
    PublishingError,
    WPAuthError,
    WPClientError,
    WPNotFoundError,
    WPRateLimitError,
)
from publishing_adapter import WordPressClient

BASE_URL = "https://example.com"
USERNAME = "editor"
APP_PASSWORD = SecretStr("abcd efgh ijkl mnop")

# The four concrete leaf error types. Exactly one of these must apply to any
# given failure (Req 7.9). They all subclass PublishingError, so mutual
# exclusivity is checked against these leaves, not the shared base.
_ALL_LEAVES = (WPAuthError, WPRateLimitError, WPNotFoundError, WPClientError)


class _Recorder:
    """Captures every request an injected transport handles."""

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


# --- Invocation dispatch: cover every public method --------------------------

_METHOD_KINDS = (
    "list_pages",
    "get_page",
    "update_page_content",
    "get_media",
    "update_media_alt_text",
)


def _invoke(client: WordPressClient, kind: str, ident: int, text: str):
    """Invoke the chosen public client method (covers all methods)."""
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

# Every failing HTTP status across the whole 4xx/5xx range (Req 7.1-7.4).
_failing_status = st.integers(min_value=400, max_value=599)

# Every httpx transport-level exception family — all wrap to WPClientError
# (Req 7.8, 12.4).
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


def _expected_status_leaf(status: int) -> type[PublishingError]:
    """The single leaf type a failing status must map to (Req 7.1-7.4, 7.9)."""
    if status in (401, 403):
        return WPAuthError
    if status == 429:
        return WPRateLimitError
    if status == 404:
        return WPNotFoundError
    return WPClientError


def _assert_exactly_one_classification(
    err: Exception, expected: type[PublishingError]
) -> None:
    """Assert ``err`` satisfies the exactly-one typed-error contract.

    * It is an instance of the expected leaf class.
    * It is NOT an instance of any sibling leaf class (mutual exclusivity of the
      concrete leaves, Req 7.9). WPClientError is the base of no other leaf, and
      the specific leaves do not subclass one another, so an exact match against
      one leaf and non-match against the rest proves "exactly one".
    * It is a PublishingError but NOT a raw httpx.HTTPError (Req 12.4).
    """
    # (1) matches the expected leaf.
    assert isinstance(err, expected), (
        f"expected {expected.__name__}, got {type(err).__name__}"
    )
    # (2) mutually exclusive with the sibling leaves — exactly one applies.
    siblings = [leaf for leaf in _ALL_LEAVES if leaf is not expected]
    for sibling in siblings:
        assert not isinstance(err, sibling), (
            f"{type(err).__name__} is also a {sibling.__name__}; "
            "classification is not exactly-one"
        )
    # The set of leaf types this error is an instance of must be exactly {expected}.
    matched = {leaf for leaf in _ALL_LEAVES if isinstance(err, leaf)}
    assert matched == {expected}, f"expected exactly {{{expected.__name__}}}, got {matched}"
    # (3) wrapped in the typed contract, never a raw httpx error (Req 12.4).
    assert isinstance(err, PublishingError)
    assert not isinstance(err, httpx.HTTPError)


# --- Property 32 -------------------------------------------------------------


@settings(max_examples=200)
@given(kind=_method_kind, ident=_ids, text=_texts, status=_failing_status)
def test_property_32_status_failure_is_classified_as_exactly_one_typed_error(
    kind: str, ident: int, text: str, status: int
) -> None:
    """Any failing HTTP status (400-599), through any method, raises exactly one
    typed PublishingError leaf per the classification rules (Req 7.1-7.4, 7.9,
    12.4).

    Feature: website-orchestrator-milestone-0, Property 32: Every failure is
    classified as exactly one typed error
    """
    rec = _Recorder()
    client = _make_client(lambda req: httpx.Response(status, json={}), rec)

    expected = _expected_status_leaf(status)
    with pytest.raises(PublishingError) as excinfo:
        _invoke(client, kind, ident, text)

    _assert_exactly_one_classification(excinfo.value, expected)


@settings(max_examples=200)
@given(kind=_method_kind, ident=_ids, text=_texts, exc_kind=_transport_exc_kind)
def test_property_32_transport_failure_is_classified_as_exactly_one_typed_error(
    kind: str, ident: int, text: str, exc_kind: str
) -> None:
    """Any httpx transport/network exception, through any method, wraps to
    exactly one typed error — WPClientError — and never propagates raw
    (Req 7.8, 7.9, 12.4).

    Feature: website-orchestrator-milestone-0, Property 32: Every failure is
    classified as exactly one typed error
    """
    rec = _Recorder()
    client = _make_client(lambda req: _raise_transport_exc(exc_kind, req), rec)

    with pytest.raises(PublishingError) as excinfo:
        _invoke(client, kind, ident, text)

    # Every transport failure classifies as exactly one leaf: WPClientError.
    _assert_exactly_one_classification(excinfo.value, WPClientError)
