"""Property 27 — Every request is authenticated with the Application_Password.

Feature: website-orchestrator-milestone-0, Property 27: Every request is
authenticated with the Application_Password

**Validates: Requirements 6.4, 6.5**

The Publishing_Adapter authenticates *every* request it issues with a WordPress
**Application_Password** over HTTP Basic auth, paired with the configured
username (Req 6.4). It never uses the account login password (Req 6.5). Because
authentication is attached per-request, no code path — read or write — can issue
an unauthenticated call.

This property asserts that, for arbitrary generated usernames and
Application_Passwords (including spaces, unicode, and other awkward values),
every request produced by every public method

    list_pages, get_page, update_page_content, get_media, update_media_alt_text

carries an ``Authorization: Basic <token>`` header whose token is exactly
``base64("<username>:<application_password>")``. The requests are captured
network-free via an injected ``httpx.MockTransport`` (returning canned ``200``
JSON), and the raw header bytes on the wire are inspected directly. Matching the
Basic token built from the *generated* credentials proves the
Application_Password — not any other/login password — is what authenticates each
request.
"""

from __future__ import annotations

import base64

import httpx
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import SecretStr

from publishing_adapter import WordPressClient

BASE_URL = "https://example.com"


class _Recorder:
    """Captures every request an injected transport handles."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []


def _make_client(
    recorder: _Recorder, username: str, application_password: str
) -> WordPressClient:
    """Build a network-free client whose transport records every request and
    returns a canned ``200`` JSON payload usable by every method."""

    def _handler(request: httpx.Request) -> httpx.Response:
        recorder.requests.append(request)
        path = request.url.path
        if "/media/" in path:
            return httpx.Response(
                200, json={"id": 1, "alt_text": "", "source_url": None}
            )
        if path.endswith("/pages"):
            # list_pages expects an array of page records.
            return httpx.Response(
                200,
                json=[{"id": 1, "content": {"rendered": ""}, "title": {"rendered": ""}}],
            )
        # A single page record for get_page / update_page_content.
        return httpx.Response(
            200, json={"id": 1, "content": {"rendered": ""}, "title": {"rendered": ""}}
        )

    transport = httpx.MockTransport(_handler)
    http_client = httpx.Client(transport=transport, base_url=BASE_URL)
    return WordPressClient(
        BASE_URL,
        username,
        SecretStr(application_password),
        client=http_client,
    )


def _expected_basic_header(username: str, application_password: str) -> str:
    """The exact ``Authorization`` header value httpx must place on the wire."""
    token = base64.b64encode(
        f"{username}:{application_password}".encode()
    ).decode()
    return f"Basic {token}"


def _exercise_all_methods(client: WordPressClient) -> None:
    """Invoke every public method so each contributes at least one request."""
    client.list_pages()
    client.get_page(1)
    client.update_page_content(1, "body")
    client.get_media(1)
    client.update_media_alt_text(1, "alt")


# Varied credentials: plain, spaces (WordPress renders Application_Passwords as
# space-separated groups), unicode, and other awkward-but-legal header material.
# ``:`` is excluded from usernames because HTTP Basic splits user:pass on the
# first colon; a colon in the username is not a meaningful WordPress case.
_usernames = st.one_of(
    st.text(
        alphabet=st.characters(
            min_codepoint=0x21, max_codepoint=0x2FFF, blacklist_characters=":"
        ),
        min_size=1,
        max_size=40,
    ),
    st.sampled_from(
        [
            "editor",
            "user name with spaces",
            "admin@example.com",
            "café_señor",
            "用户",
            "😀-emoji-user",
        ]
    ),
)

_app_passwords = st.one_of(
    st.text(min_size=1, max_size=60),
    st.text(
        alphabet=st.characters(min_codepoint=0x80, max_codepoint=0x2FFF),
        min_size=1,
        max_size=40,
    ),
    st.sampled_from(
        [
            "abcd efgh ijkl mnop qrst uvwx",  # WordPress-style Application_Password
            "single",
            "   leading and trailing spaces   ",
            "unicode-café-你好-😀",
            "symbols!@#$%^&*()_+-=[]{}",
        ]
    ),
)


@settings(max_examples=100)
@given(username=_usernames, application_password=_app_passwords)
def test_property_27_every_request_uses_application_password(
    username: str, application_password: str
) -> None:
    """Every request from every method carries HTTP Basic auth built from the
    generated username + Application_Password (Req 6.4, 6.5).

    Feature: website-orchestrator-milestone-0, Property 27: Every request is
    authenticated with the Application_Password
    """
    rec = _Recorder()
    client = _make_client(rec, username, application_password)

    _exercise_all_methods(client)

    expected = _expected_basic_header(username, application_password)
    # Every public method issued at least one request.
    assert len(rec.requests) >= 5
    # And EVERY captured request authenticates with the Application_Password —
    # never an unauthenticated call, never a different credential.
    for request in rec.requests:
        auth = request.headers.get("authorization")
        assert auth is not None, "a request was issued without authentication"
        assert auth == expected
        # The Basic token must decode back to exactly the generated credentials,
        # proving the Application_Password (not a login password) is in use.
        scheme, _, token = auth.partition(" ")
        assert scheme == "Basic"
        decoded = base64.b64decode(token).decode()
        assert decoded == f"{username}:{application_password}"
