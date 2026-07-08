"""Property 26 — Writes touch only allowed fields.

Feature: website-orchestrator-milestone-0, Property 26: Writes touch only
allowed fields.

**Validates: Requirements 6.2, 6.3**

The Publishing_Adapter is the only subsystem with write access to the live
WordPress site, and its writes are tightly scoped (Req 6.2, 6.3):

* :meth:`WordPressClient.update_page_content` may write *only* the page/post
  ``content`` field — never meta descriptions, schema/JSON-LD, ``title``,
  ``slug``, ``status``, or any other field.
* :meth:`WordPressClient.update_media_alt_text` may write *only* the media
  ``alt_text`` field.

These properties assert that, for arbitrary ids and arbitrary payload strings
(unicode, empty, very long, HTML), the request body actually placed on the wire
contains **exactly** the single permitted key with the exact input value and
nothing else. The request is captured network-free via an injected
``httpx.MockTransport``, and its raw body is parsed as JSON and inspected
directly, so this checks the serialized bytes rather than the client's internal
intent.
"""

from __future__ import annotations

import json

import httpx
from hypothesis import given
from hypothesis import strategies as st
from pydantic import SecretStr

from publishing_adapter import WordPressClient

BASE_URL = "https://example.com"
USERNAME = "editor"
APP_PASSWORD = SecretStr("abcd efgh ijkl mnop")

# Metadata/schema/other fields that must NEVER appear in ANY scoped write body
# (Req 6.2, 6.3). Writing any of these would let the adapter modify content it
# is not permitted to touch. The single allowed field per method is checked
# separately via an exact key-set assertion.
_FORBIDDEN_FIELDS = frozenset(
    {
        "title",
        "meta",
        "slug",
        "status",
        "excerpt",
        "author",
        "date",
        "schema",
        "yoast_head",
        "featured_media",
        "categories",
        "tags",
    }
)


class _Recorder:
    """Captures every request an injected transport handles."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []


def _make_client(recorder: _Recorder) -> WordPressClient:
    """Build a network-free client whose transport records + echoes requests."""

    def _handler(request: httpx.Request) -> httpx.Response:
        recorder.requests.append(request)
        body = json.loads(request.content) if request.content else {}
        # Echo the written field back so the client can parse a valid record.
        if "content" in body:
            return httpx.Response(
                200, json={"id": 1, "content": {"rendered": body["content"]}}
            )
        return httpx.Response(
            200, json={"id": 1, "alt_text": body.get("alt_text", "")}
        )

    transport = httpx.MockTransport(_handler)
    http_client = httpx.Client(transport=transport, base_url=BASE_URL)
    return WordPressClient(BASE_URL, USERNAME, APP_PASSWORD, client=http_client)


# Varied payloads: empty, plain, unicode, HTML, and long strings all in scope.
_payload_text = st.one_of(
    st.text(),
    st.text(
        alphabet=st.characters(min_codepoint=0x80, max_codepoint=0x2FFF),
        min_size=1,
    ),
    st.sampled_from(
        [
            "",
            " ",
            "<p>Hello <strong>world</strong></p>",
            "<script>alert('x')</script>",
            "café — naïve — 你好 — 😀",
            "A" * 5000,
            '{"title": "injection attempt", "meta": "x"}',
            "line1\nline2\ttabbed",
        ]
    ),
)

_ids = st.integers(min_value=1, max_value=2**31 - 1)


@given(page_id=_ids, content=_payload_text)
def test_update_page_content_writes_only_content_field(
    page_id: int, content: str
) -> None:
    """update_page_content sends a body of exactly ``{"content": <input>}``."""
    rec = _Recorder()
    client = _make_client(rec)

    client.update_page_content(page_id, content)

    assert len(rec.requests) == 1
    sent = rec.requests[-1]
    assert sent.method == "POST"
    assert sent.url.path == f"/wp-json/wp/v2/pages/{page_id}"

    body = json.loads(sent.content)
    # Exactly the one permitted key — nothing else.
    assert set(body.keys()) == {"content"}
    assert body["content"] == content
    # No forbidden/other field ever leaks in (title, meta, slug, status, ...).
    assert _FORBIDDEN_FIELDS.intersection(body.keys()) == set()


@given(media_id=_ids, alt_text=_payload_text)
def test_update_media_alt_text_writes_only_alt_text_field(
    media_id: int, alt_text: str
) -> None:
    """update_media_alt_text sends a body of exactly ``{"alt_text": <input>}``."""
    rec = _Recorder()
    client = _make_client(rec)

    client.update_media_alt_text(media_id, alt_text)

    assert len(rec.requests) == 1
    sent = rec.requests[-1]
    assert sent.method == "POST"
    assert sent.url.path == f"/wp-json/wp/v2/media/{media_id}"

    body = json.loads(sent.content)
    # Exactly the one permitted key — nothing else.
    assert set(body.keys()) == {"alt_text"}
    assert body["alt_text"] == alt_text
    # No forbidden/other field ever leaks in.
    assert _FORBIDDEN_FIELDS.intersection(body.keys()) == set()
