"""Unit tests for :class:`publishing_adapter.client.WordPressClient` (task 10.1).

These cover the happy-path methods, per-request HTTP Basic authentication with
the Application_Password, the missing-credential guard that fires before any
request, scoped writes (only ``content`` / ``alt_text``), and credential
non-leakage. All tests are network-free via an injected ``httpx.MockTransport``.
"""

from __future__ import annotations

import base64

import httpx
import pytest
from pydantic import SecretStr

from core.exceptions import (
    MissingCredentialError,
    WPAuthError,
    WPClientError,
    WPNotFoundError,
    WPRateLimitError,
)
from core.interfaces import WPMedia, WPPage
from publishing_adapter import WordPressClient

BASE_URL = "https://example.com"
USERNAME = "editor"
APP_PASSWORD = "abcd efgh ijkl mnop"  # WordPress-style Application_Password.


class _Recorder:
    """Captures every request an injected transport handles."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []


def _make_client(
    handler,
    *,
    application_password: SecretStr | str | None = APP_PASSWORD,
    recorder: _Recorder | None = None,
) -> WordPressClient:
    rec = recorder or _Recorder()

    def _wrapped(request: httpx.Request) -> httpx.Response:
        rec.requests.append(request)
        return handler(request)

    transport = httpx.MockTransport(_wrapped)
    http_client = httpx.Client(transport=transport, base_url=BASE_URL)
    return WordPressClient(
        BASE_URL, USERNAME, application_password, client=http_client
    )


def _expected_basic_header() -> str:
    token = base64.b64encode(f"{USERNAME}:{APP_PASSWORD}".encode()).decode()
    return f"Basic {token}"


# --- Import / instantiation --------------------------------------------------


def test_client_is_importable_and_instantiable() -> None:
    client = _make_client(lambda req: httpx.Response(200, json=[]))
    assert isinstance(client, WordPressClient)


# --- Happy-path reads/writes -------------------------------------------------


def test_list_pages_returns_wppages() -> None:
    payload = [
        {"id": 1, "content": {"rendered": "<p>one</p>"}, "title": {"rendered": "One"}, "link": "https://example.com/1"},
        {"id": 2, "content": {"rendered": "<p>two</p>"}, "title": {"rendered": "Two"}, "link": "https://example.com/2"},
    ]
    client = _make_client(lambda req: httpx.Response(200, json=payload))
    pages = client.list_pages()
    assert [p.id for p in pages] == [1, 2]
    assert all(isinstance(p, WPPage) for p in pages)
    assert pages[0].content == "<p>one</p>"
    assert pages[0].title == "One"


def test_get_page_hits_correct_endpoint() -> None:
    rec = _Recorder()
    client = _make_client(
        lambda req: httpx.Response(200, json={"id": 7, "content": {"rendered": "hi"}}),
        recorder=rec,
    )
    page = client.get_page(7)
    assert page == WPPage(id=7, content="hi")
    assert rec.requests[-1].url.path == "/wp-json/wp/v2/pages/7"
    assert rec.requests[-1].method == "GET"


def test_get_media_returns_wpmedia() -> None:
    rec = _Recorder()
    client = _make_client(
        lambda req: httpx.Response(
            200, json={"id": 42, "alt_text": "a cat", "source_url": "https://example.com/cat.jpg"}
        ),
        recorder=rec,
    )
    media = client.get_media(42)
    assert media == WPMedia(id=42, alt_text="a cat", source_url="https://example.com/cat.jpg")
    assert isinstance(media, WPMedia)
    assert rec.requests[-1].url.path == "/wp-json/wp/v2/media/42"


# --- Authentication (Req 6.4, 6.5) -------------------------------------------


def test_every_request_carries_basic_auth() -> None:
    rec = _Recorder()
    client = _make_client(
        lambda req: httpx.Response(200, json={"id": 1, "content": {"rendered": "x"}}),
        recorder=rec,
    )
    client.get_page(1)
    client.update_page_content(1, "new")
    client.get_media(1)
    assert rec.requests, "expected at least one request"
    for request in rec.requests:
        assert request.headers.get("authorization") == _expected_basic_header()


# --- Missing-credential guard (Req 6.6) --------------------------------------


@pytest.mark.parametrize("missing", [None, "", SecretStr("")])
def test_missing_application_password_raises_before_any_request(missing) -> None:
    rec = _Recorder()
    client = _make_client(
        lambda req: httpx.Response(200, json=[]),
        application_password=missing,
        recorder=rec,
    )
    for call in (
        client.list_pages,
        lambda: client.get_page(1),
        lambda: client.update_page_content(1, "c"),
        lambda: client.get_media(1),
        lambda: client.update_media_alt_text(1, "alt"),
    ):
        with pytest.raises(MissingCredentialError):
            call()
    # No request was ever issued.
    assert rec.requests == []


# --- Scoped writes (Req 6.2, 6.3) --------------------------------------------


def test_update_page_content_writes_only_content_field() -> None:
    rec = _Recorder()
    client = _make_client(
        lambda req: httpx.Response(200, json={"id": 5, "content": {"rendered": "updated"}}),
        recorder=rec,
    )
    result = client.update_page_content(5, "updated")
    assert result.content == "updated"
    sent = rec.requests[-1]
    assert sent.method == "POST"
    assert sent.url.path == "/wp-json/wp/v2/pages/5"
    import json as _json

    body = _json.loads(sent.content)
    assert body == {"content": "updated"}


def test_update_media_alt_text_writes_only_alt_text_field() -> None:
    rec = _Recorder()
    client = _make_client(
        lambda req: httpx.Response(200, json={"id": 9, "alt_text": "described"}),
        recorder=rec,
    )
    result = client.update_media_alt_text(9, "described")
    assert result.alt_text == "described"
    sent = rec.requests[-1]
    assert sent.method == "POST"
    assert sent.url.path == "/wp-json/wp/v2/media/9"
    import json as _json

    body = _json.loads(sent.content)
    assert body == {"alt_text": "described"}


# --- Credential non-leakage (Req 6.7, 7.5, 7.10) -----------------------------


def test_repr_does_not_leak_credential() -> None:
    client = _make_client(lambda req: httpx.Response(200, json=[]))
    text = repr(client)
    assert APP_PASSWORD not in text
    assert USERNAME in text  # username is not a secret


def test_missing_credential_error_does_not_contain_value() -> None:
    err = MissingCredentialError("Application_Password")
    assert APP_PASSWORD not in str(err)
    assert "Application_Password" in str(err)


def test_returned_records_contain_no_credential() -> None:
    client = _make_client(
        lambda req: httpx.Response(200, json={"id": 1, "content": {"rendered": "body"}})
    )
    page = client.get_page(1)
    assert APP_PASSWORD not in page.model_dump_json()


# --- Failure classification (Req 7.1-7.4, 7.8, 7.9, 12.4) --------------------


@pytest.mark.parametrize("status", [401, 403])
def test_auth_failure_raises_wpautherror(status) -> None:
    client = _make_client(lambda req: httpx.Response(status, json={}))
    with pytest.raises(WPAuthError):
        client.get_page(1)


def test_rate_limit_raises_wpratelimiterror() -> None:
    client = _make_client(lambda req: httpx.Response(429, json={}))
    with pytest.raises(WPRateLimitError):
        client.get_page(1)


def test_not_found_raises_wpnotfounderror() -> None:
    client = _make_client(lambda req: httpx.Response(404, json={}))
    with pytest.raises(WPNotFoundError):
        client.get_page(1)


@pytest.mark.parametrize("status", [400, 409, 422, 500, 502, 503])
def test_other_failures_raise_wpclienterror(status) -> None:
    client = _make_client(lambda req: httpx.Response(status, json={}))
    with pytest.raises(WPClientError):
        client.get_page(1)


def test_timeout_raises_wpclienterror_wrapped_not_raw() -> None:
    def _handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timed out", request=request)

    client = _make_client(_handler)
    # A raw httpx.TimeoutException must NOT escape; it is wrapped (Req 7.8, 12.4).
    with pytest.raises(WPClientError) as excinfo:
        client.get_page(1)
    assert not isinstance(excinfo.value, httpx.HTTPError)


def test_transport_error_raises_wpclienterror_wrapped_not_raw() -> None:
    def _handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    client = _make_client(_handler)
    with pytest.raises(WPClientError) as excinfo:
        client.get_page(1)
    assert not isinstance(excinfo.value, httpx.HTTPError)


def test_each_status_maps_to_exactly_one_error_type() -> None:
    # Every failed status is classified as exactly one typed error (Req 7.9):
    # narrower types must not also be catchable as a sibling type.
    cases = {
        401: (WPAuthError, (WPRateLimitError, WPNotFoundError)),
        429: (WPRateLimitError, (WPAuthError, WPNotFoundError)),
        404: (WPNotFoundError, (WPAuthError, WPRateLimitError)),
        500: (WPClientError, (WPAuthError, WPRateLimitError, WPNotFoundError)),
    }
    for status, (expected, others) in cases.items():
        client = _make_client(lambda req, s=status: httpx.Response(s, json={}))
        with pytest.raises(expected) as excinfo:
            client.get_page(1)
        assert not isinstance(excinfo.value, others)


# --- Single attempt / no retry (Req 7.6) -------------------------------------


def test_failure_makes_exactly_one_attempt_no_retry() -> None:
    rec = _Recorder()
    client = _make_client(
        lambda req: httpx.Response(500, json={}), recorder=rec
    )
    with pytest.raises(WPClientError):
        client.update_page_content(1, "content")
    # No retry logic: the transport was invoked exactly once on failure.
    assert len(rec.requests) == 1


def test_timeout_makes_exactly_one_attempt_no_retry() -> None:
    rec = _Recorder()

    def _handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timed out", request=request)

    client = _make_client(_handler, recorder=rec)
    with pytest.raises(WPClientError):
        client.get_page(1)
    assert len(rec.requests) == 1


# --- Idempotency (Req 7.7) ---------------------------------------------------


def test_repeated_page_write_same_value_is_idempotent() -> None:
    # WordPress POSTs to a fixed id; repeating the same write updates the same
    # resource, creates no duplicate, converges to the target, and never raises.
    rec = _Recorder()
    live = {"content": "old"}

    def _handler(request: httpx.Request) -> httpx.Response:
        import json as _json

        body = _json.loads(request.content)
        live["content"] = body["content"]
        return httpx.Response(
            200, json={"id": 5, "content": {"rendered": live["content"]}}
        )

    client = _make_client(_handler, recorder=rec)
    first = client.update_page_content(5, "target")
    second = client.update_page_content(5, "target")

    assert first.content == "target"
    assert second.content == "target"
    assert live["content"] == "target"  # live state equals the target value
    # Both writes hit the same fixed resource id — no duplicate creation.
    paths = [r.url.path for r in rec.requests]
    assert paths == ["/wp-json/wp/v2/pages/5", "/wp-json/wp/v2/pages/5"]


def test_repeated_media_write_same_value_is_idempotent() -> None:
    rec = _Recorder()
    live = {"alt_text": "old"}

    def _handler(request: httpx.Request) -> httpx.Response:
        import json as _json

        body = _json.loads(request.content)
        live["alt_text"] = body["alt_text"]
        return httpx.Response(200, json={"id": 9, "alt_text": live["alt_text"]})

    client = _make_client(_handler, recorder=rec)
    first = client.update_media_alt_text(9, "described")
    second = client.update_media_alt_text(9, "described")

    assert first.alt_text == "described"
    assert second.alt_text == "described"
    assert live["alt_text"] == "described"
    paths = [r.url.path for r in rec.requests]
    assert paths == ["/wp-json/wp/v2/media/9", "/wp-json/wp/v2/media/9"]


# --- Credential non-leakage in classified errors (Req 7.5, 7.10) -------------


@pytest.mark.parametrize("status", [401, 403, 404, 429, 500])
def test_status_errors_do_not_leak_credential(status) -> None:
    client = _make_client(lambda req: httpx.Response(status, json={}))
    with pytest.raises(Exception) as excinfo:
        client.get_page(1)
    err = excinfo.value
    text = f"{err!s} {err.args!r}"
    assert APP_PASSWORD not in text
    for word in APP_PASSWORD.split():
        assert word not in text


def test_timeout_error_does_not_leak_credential() -> None:
    def _handler(request: httpx.Request) -> httpx.Response:
        # Simulate an httpx error whose message echoes request material; the
        # wrapped error must not surface it.
        raise httpx.TimeoutException(
            f"timed out talking to {request.url}", request=request
        )

    client = _make_client(_handler)
    with pytest.raises(WPClientError) as excinfo:
        client.get_page(1)
    err = excinfo.value
    text = f"{err!s} {err.args!r}"
    assert APP_PASSWORD not in text
    for word in APP_PASSWORD.split():
        assert word not in text
