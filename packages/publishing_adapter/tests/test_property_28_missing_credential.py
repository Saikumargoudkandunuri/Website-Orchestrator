"""Property 28 — Missing Application_Password prevents any request.

Feature: website-orchestrator-milestone-0, Property 28: Missing
Application_Password prevents any request.

**Validates: Requirements 6.6**

The Publishing_Adapter must never issue a WordPress request when the
Application_Password is missing or unconfigured. Instead, every public method
raises :class:`~core.exceptions.MissingCredentialError` *before* any request is
attempted (Req 6.6).

This property asserts that, for arbitrary usernames and arbitrary method
arguments (page ids, media ids, content, alt text), and for each shape a
missing credential can take (``None``, the empty string ``""``, and an empty
:class:`~pydantic.SecretStr`), calling **any** of the five public methods
(:meth:`~publishing_adapter.client.WordPressClient.list_pages`,
:meth:`~publishing_adapter.client.WordPressClient.get_page`,
:meth:`~publishing_adapter.client.WordPressClient.update_page_content`,
:meth:`~publishing_adapter.client.WordPressClient.get_media`,
:meth:`~publishing_adapter.client.WordPressClient.update_media_alt_text`)
raises ``MissingCredentialError`` AND leaves the injected transport with a
recording of **zero** requests — proving no request was ever placed on the wire.

The transport is an ``httpx.MockTransport`` that appends every handled request
to a recorder; if the guard failed and a request escaped, the recorder would be
non-empty and the test would fail.
"""

from __future__ import annotations

import httpx
import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import SecretStr

from core.exceptions import MissingCredentialError
from publishing_adapter import WordPressClient

BASE_URL = "https://example.com"

# Every shape a "missing/unconfigured" Application_Password can take (Req 6.6):
# absent (None), empty plain string, and an empty SecretStr.
_MISSING_CREDENTIALS: list[SecretStr | str | None] = [None, "", SecretStr("")]


class _Recorder:
    """Captures every request an injected transport handles."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []


def _make_client(
    recorder: _Recorder,
    *,
    username: str,
    application_password: SecretStr | str | None,
) -> WordPressClient:
    """Build a network-free client whose transport records every request.

    If any method were to (wrongly) issue a request despite the missing
    credential, ``recorder.requests`` would capture it. A correct guard fires
    first, so the handler below must never run.
    """

    def _handler(request: httpx.Request) -> httpx.Response:
        recorder.requests.append(request)
        # Return a benign success; reaching here at all means the guard failed.
        return httpx.Response(200, json=[])

    transport = httpx.MockTransport(_handler)
    http_client = httpx.Client(transport=transport, base_url=BASE_URL)
    return WordPressClient(
        BASE_URL, username, application_password, client=http_client
    )


# Varied usernames: typical logins, empty, unicode, whitespace, and long.
_usernames = st.one_of(
    st.text(),
    st.sampled_from(
        [
            "",
            "editor",
            "admin",
            " ",
            "user name with spaces",
            "üsernäme",
            "用户",
            "a" * 256,
        ]
    ),
)

# Varied resource ids for the id-taking methods.
_ids = st.integers(min_value=1, max_value=2**31 - 1)

# Varied text payloads for the write methods.
_text = st.one_of(
    st.text(),
    st.sampled_from(
        [
            "",
            "<p>Hello <strong>world</strong></p>",
            "café — naïve — 你好 — 😀",
            "A" * 5000,
        ]
    ),
)


@given(
    missing=st.sampled_from(_MISSING_CREDENTIALS),
    username=_usernames,
    page_id=_ids,
    media_id=_ids,
    content=_text,
    alt_text=_text,
)
def test_missing_application_password_prevents_any_request(
    missing: SecretStr | str | None,
    username: str,
    page_id: int,
    media_id: int,
    content: str,
    alt_text: str,
) -> None:
    """Every method raises MissingCredentialError and issues zero requests.

    For each generated username and each missing-credential shape, all five
    public methods must raise ``MissingCredentialError`` and leave the recorder
    empty (no request was ever issued) — Req 6.6.
    """
    rec = _Recorder()
    client = _make_client(
        rec, username=username, application_password=missing
    )

    # Each public method, exercised with varied arguments.
    calls = [
        client.list_pages,
        lambda: client.get_page(page_id),
        lambda: client.update_page_content(page_id, content),
        lambda: client.get_media(media_id),
        lambda: client.update_media_alt_text(media_id, alt_text),
    ]

    for call in calls:
        with pytest.raises(MissingCredentialError):
            call()
        # The guard fired before any network activity: zero requests recorded.
        assert rec.requests == [], (
            "a request was issued despite a missing Application_Password"
        )

    # No method, across the whole sweep, ever placed a request on the wire.
    assert rec.requests == []
