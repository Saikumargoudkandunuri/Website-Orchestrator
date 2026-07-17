"""Milestone 5 — RankMath/OG/Twitter/canonical postmeta write scoping.

``WordPressClient.update_page_meta`` is the write path the Automatic Blog
Writer (AI Writer V2) uses for RankMath/OG/Twitter/canonical fields. It must
write *only* a ``meta`` object containing exactly the supplied keys — never any
other page field (title/slug/status/content/etc.) — mirroring the same
allowed-fields discipline already proven for ``update_page_content`` /
``update_media_alt_text`` (Req 6.2, 6.3).
"""

from __future__ import annotations

import json

import httpx
from pydantic import SecretStr

from publishing_adapter import WordPressClient

BASE_URL = "https://example.com"
USERNAME = "editor"
APP_PASSWORD = SecretStr("abcd efgh ijkl mnop")

_FORBIDDEN_FIELDS = frozenset({"title", "slug", "status", "content", "excerpt", "author"})


class _Recorder:
    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []


def _make_client(recorder: _Recorder, *, existing_meta: dict | None = None) -> WordPressClient:
    def _handler(request: httpx.Request) -> httpx.Response:
        recorder.requests.append(request)
        if request.method == "GET":
            return httpx.Response(200, json={"id": 1, "content": {"rendered": ""}, "meta": existing_meta or {}})
        body = json.loads(request.content) if request.content else {}
        return httpx.Response(200, json={"id": 1, "content": {"rendered": ""}, "meta": body.get("meta", {})})

    transport = httpx.MockTransport(_handler)
    http_client = httpx.Client(transport=transport, base_url=BASE_URL)
    return WordPressClient(BASE_URL, USERNAME, APP_PASSWORD, client=http_client)


def test_update_page_meta_writes_only_meta_object() -> None:
    rec = _Recorder()
    client = _make_client(rec)

    meta = {"rank_math_title": "SEO Title", "rank_math_canonical_url": "https://example.com/"}
    result = client.update_page_meta(1, meta)

    assert len(rec.requests) == 1
    sent = rec.requests[-1]
    assert sent.method == "POST"
    assert sent.url.path == "/wp-json/wp/v2/pages/1"

    body = json.loads(sent.content)
    assert set(body.keys()) == {"meta"}
    assert body["meta"] == meta
    assert _FORBIDDEN_FIELDS.intersection(body.keys()) == set()
    assert result == meta


def test_get_page_meta_reads_existing_meta_object() -> None:
    rec = _Recorder()
    client = _make_client(rec, existing_meta={"rank_math_title": "Existing Title"})

    result = client.get_page_meta(1)

    assert result == {"rank_math_title": "Existing Title"}
    assert rec.requests[-1].method == "GET"


def test_get_page_meta_returns_empty_when_no_meta_registered() -> None:
    rec = _Recorder()
    client = _make_client(rec, existing_meta=None)

    result = client.get_page_meta(1)

    assert result == {}
