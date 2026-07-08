"""Property 29 — Credentials never leak through returns or errors.

Feature: website-orchestrator-milestone-0, Property 29: Credentials never leak
through returns or errors

**Validates: Requirements 6.7, 7.10**

The WordPress Application_Password authenticates every request over HTTP Basic
(Req 6.4, 6.5), but it must live *only* in the request headers. The adapter must
never surface it — not through a returned value, and not through a raised error
(Req 6.7, 7.10):

* Req 6.7 — the Publishing_Adapter SHALL NOT include any credential in returned
  values or raised errors.
* Req 7.10 — the Publishing_Adapter SHALL NOT include any credential in the
  message or attributes of any raised error.

This property drives arbitrary Application_Passwords (WordPress-shaped
space-separated groups, plain, and unicode) through **both** the success and the
failure paths of every public method, then inspects every text surface the
caller can observe:

* **Success** — for ``get_page`` / ``get_media`` / ``list_pages`` /
  ``update_page_content`` / ``update_media_alt_text`` the transport returns a
  ``200`` JSON body. The returned model's ``model_dump_json()`` and
  ``repr(client)`` must contain neither the full secret nor any of its
  space-separated words.
* **Failure** — the transport returns ``401`` / ``403`` / ``404`` / ``429`` /
  ``500`` or raises a transport timeout / connection error. The raised
  exception's ``str(exc)`` and ``repr(exc.args)`` must contain neither the full
  secret nor any of its space-separated words.

All requests are network-free via an injected ``httpx.MockTransport``.

Robustness note — a randomly generated secret word could, by pure chance, be a
substring of a *legitimate* surface (a URL, the username, a JSON key, or a fixed
error-template word). That would be a false positive unrelated to any leak, so a
Hypothesis ``assume`` filters those rare collisions out against a precomputed
corpus of every constant string the client may legitimately emit. What remains
is exactly the leak signal: if a secret (or word of it) appears in a surface, it
can only be because the client copied it there.
"""

from __future__ import annotations

import json

import httpx
import pytest
from hypothesis import assume, given, settings
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

BASE_URL = "https://wp.example.test"
USERNAME = "editor"

# Fixed, credential-free values the mocked WordPress returns on the success
# path. Chosen to be simple ascii so the "safe corpus" (below) is exhaustive.
_PAGE_CONTENT = "safe body content value"
_PAGE_TITLE = "safe page title value"
_PAGE_LINK = f"{BASE_URL}/pages/1"
_MEDIA_ALT = "safe media alt value"
_MEDIA_SOURCE = f"{BASE_URL}/wp-content/uploads/pic.jpg"


# --- Safe corpus: everything the client may legitimately surface -------------
#
# Every string a caller can observe from the client that is NOT the credential:
# the base URL and username, the repr labels, all JSON keys/values of the
# returned models, and every error-message template (with each status code and
# each wrapped-exception type name). A generated secret word that happens to be
# a substring of this corpus is a coincidental collision, not a leak, and is
# filtered with ``assume`` so the test measures only real leakage.
def _error_templates() -> list[str]:
    templates: list[str] = []
    for status in (401, 403):
        templates.append(f"WordPress authentication failed (HTTP {status})")
    templates.append("WordPress request was rate limited (HTTP 429)")
    templates.append("WordPress resource not found (HTTP 404)")
    for status in (400, 402, 405, 409, 422, 500, 502, 503):
        templates.append(f"WordPress request failed with status {status}")
    templates.append("WordPress request timed out (TimeoutException)")
    templates.append("WordPress request timed out (ReadTimeout)")
    templates.append("WordPress request timed out (ConnectTimeout)")
    templates.append("WordPress request failed (ConnectError)")
    templates.append("WordPress request failed (ReadError)")
    return templates


_SAFE_CORPUS = " ".join(
    [
        BASE_URL,
        USERNAME,
        # repr(client) label surface.
        "WordPressClient",
        "base_url",
        "username",
        # WPPage / WPMedia model_dump_json keys + our fixed values.
        "id",
        "content",
        "title",
        "link",
        "alt_text",
        "source_url",
        _PAGE_CONTENT,
        _PAGE_TITLE,
        _PAGE_LINK,
        _MEDIA_ALT,
        _MEDIA_SOURCE,
        # Structural JSON punctuation the dump may contain.
        "null true false",
        *_error_templates(),
    ]
)


# --- Application_Password strategy -------------------------------------------
#
# Words are letters/digits (incl. unicode letters), min length 4 so they are
# "non-trivial" and unlikely to coincidentally collide with the safe corpus.
_pw_word = st.text(
    alphabet=st.characters(categories=("Ll", "Lu", "Nd", "Lo")),
    min_size=4,
    max_size=10,
)

_generated_password = st.lists(_pw_word, min_size=1, max_size=6).map(
    lambda words: " ".join(words)
)

_app_password = st.one_of(
    _generated_password,
    # Realistic WordPress-issued shapes: four groups of four characters.
    st.sampled_from(
        [
            "abcd efgh ijkl mnop",
            "wXyz 12ab QQ7p k9Lm",
            "AAAA BBBB CCCC DDDD",
            "s3cr 3tPw dZZ9 Qw12",
        ]
    ),
    # Unicode / mixed secrets with embedded spaces.
    st.sampled_from(
        [
            "café naïve señor über",
            "пароль секрет ключ токен",
            "秘密 密码 令牌 認證",
            "Straße Ölfaß Mötörhead",
        ]
    ),
)


def _secret_words(secret: str) -> list[str]:
    """The credential's space-separated words (empties dropped)."""
    return [w for w in secret.split(" ") if w]


class _Recorder:
    """Captures every request an injected transport handles."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []


def _make_client(handler, app_password: str, rec: _Recorder) -> WordPressClient:
    """Build a network-free client whose transport records + runs ``handler``."""

    def _wrapped(request: httpx.Request) -> httpx.Response:
        rec.requests.append(request)
        return handler(request)

    transport = httpx.MockTransport(_wrapped)
    http_client = httpx.Client(transport=transport, base_url=BASE_URL)
    return WordPressClient(
        BASE_URL, USERNAME, SecretStr(app_password), client=http_client
    )


def _assert_absent(secret: str, text: str) -> None:
    """The full secret and each of its words must be absent from ``text``."""
    assert secret not in text
    for word in _secret_words(secret):
        assert word not in text


def _success_handler(request: httpx.Request) -> httpx.Response:
    """A 200 response for any read/write on the success path."""
    if "/media/" in request.url.path:
        return httpx.Response(
            200,
            json={
                "id": 1,
                "alt_text": _MEDIA_ALT,
                "source_url": _MEDIA_SOURCE,
            },
        )
    if request.url.path.endswith("/pages"):
        page = {
            "id": 1,
            "content": {"rendered": _PAGE_CONTENT},
            "title": {"rendered": _PAGE_TITLE},
            "link": _PAGE_LINK,
        }
        return httpx.Response(200, json=[page, {**page, "id": 2}])
    return httpx.Response(
        200,
        json={
            "id": 1,
            "content": {"rendered": _PAGE_CONTENT},
            "title": {"rendered": _PAGE_TITLE},
            "link": _PAGE_LINK,
        },
    )


# --- Property 29 (success path) ----------------------------------------------

_SUCCESS_METHODS = st.sampled_from(
    ["get_page", "get_media", "list_pages", "update_page", "update_media"]
)


@settings(max_examples=200, deadline=None)
@given(app_password=_app_password, method=_SUCCESS_METHODS)
def test_success_returns_never_leak_credential(
    app_password: str, method: str
) -> None:
    """No successful return value (nor ``repr(client)``) exposes the secret.

    Feature: website-orchestrator-milestone-0, Property 29: Credentials never
    leak through returns or errors

    Validates: Requirements 6.7
    """
    # Skip coincidental collisions of a random secret word with a legitimate
    # surface — those are not leaks (see module docstring).
    assume(app_password not in _SAFE_CORPUS)
    assume(all(word not in _SAFE_CORPUS for word in _secret_words(app_password)))

    rec = _Recorder()
    client = _make_client(_success_handler, app_password, rec)

    if method == "get_page":
        surfaces = [client.get_page(1).model_dump_json()]
    elif method == "get_media":
        surfaces = [client.get_media(1).model_dump_json()]
    elif method == "list_pages":
        surfaces = [p.model_dump_json() for p in client.list_pages()]
    elif method == "update_page":
        surfaces = [client.update_page_content(1, "new body").model_dump_json()]
    else:  # update_media
        surfaces = [client.update_media_alt_text(1, "new alt").model_dump_json()]

    # A request was actually issued (the secret rode in the auth header only).
    assert rec.requests
    for surface in surfaces:
        _assert_absent(app_password, surface)
    # The client's own repr must never render the credential either.
    _assert_absent(app_password, repr(client))


# --- Property 29 (failure path) ----------------------------------------------

# Each failure mode maps to exactly one typed PublishingError. We assert the
# credential is absent regardless of which typed error is raised.
_STATUS_FAILURES = [
    (401, WPAuthError),
    (403, WPAuthError),
    (404, WPNotFoundError),
    (429, WPRateLimitError),
    (500, WPClientError),
    (502, WPClientError),
]

_TRANSPORT_FAILURES = ["timeout", "connect"]

_FAILURE_MODES = st.one_of(
    st.sampled_from([f"status:{s}" for s, _ in _STATUS_FAILURES]),
    st.sampled_from([f"transport:{t}" for t in _TRANSPORT_FAILURES]),
)

_FAILURE_METHODS = st.sampled_from(
    ["get_page", "get_media", "list_pages", "update_page", "update_media"]
)


@settings(max_examples=200, deadline=None)
@given(
    app_password=_app_password,
    mode=_FAILURE_MODES,
    method=_FAILURE_METHODS,
)
def test_raised_errors_never_leak_credential(
    app_password: str, mode: str, method: str
) -> None:
    """No raised error's message or ``args`` exposes the secret.

    Feature: website-orchestrator-milestone-0, Property 29: Credentials never
    leak through returns or errors

    Validates: Requirements 7.10
    """
    assume(app_password not in _SAFE_CORPUS)
    assume(all(word not in _SAFE_CORPUS for word in _secret_words(app_password)))

    kind, _, spec = mode.partition(":")

    if kind == "status":
        status = int(spec)

        def _handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(status, json={"error": "denied"})

    else:  # transport failure — the underlying httpx error echoes request info,
        # including the URL that carries no secret; the wrapped error must still
        # be scrubbed to the exception type only.
        def _handler(request: httpx.Request) -> httpx.Response:
            if spec == "timeout":
                raise httpx.TimeoutException(
                    f"timed out talking to {request.url}", request=request
                )
            raise httpx.ConnectError(
                f"connection refused for {request.url}", request=request
            )

    rec = _Recorder()
    client = _make_client(_handler, app_password, rec)

    calls = {
        "get_page": lambda: client.get_page(1),
        "get_media": lambda: client.get_media(1),
        "list_pages": client.list_pages,
        "update_page": lambda: client.update_page_content(1, "new body"),
        "update_media": lambda: client.update_media_alt_text(1, "new alt"),
    }

    with pytest.raises(PublishingError) as excinfo:
        calls[method]()

    err = excinfo.value
    text = f"{err!s} {err.args!r}"
    _assert_absent(app_password, text)
    # Also inspect the credential-free repr of the exception itself.
    _assert_absent(app_password, repr(err))
