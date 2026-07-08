"""Property 31 — Repeated writes are idempotent.

Feature: website-orchestrator-milestone-0, Property 31: Repeated writes are
idempotent.

**Validates: Requirements 7.7**

The Publishing_Adapter's two write methods
(:meth:`WordPressClient.update_page_content`,
:meth:`WordPressClient.update_media_alt_text`) POST to a **fixed resource id**
(``.../pages/{id}`` / ``.../media/{id}``) with the target value in the body.
WordPress treats such a POST as a field update on an existing resource, not a
creation, so applying the same write repeatedly with the same value is naturally
idempotent (Req 7.7): the live state converges to the target value, no duplicate
resource is created, and a repeated successful write returns success rather than
raising.

These properties drive that guarantee with a **stateful** network-free
``httpx.MockTransport``. The handler keeps an in-memory ``live`` dict keyed by
resource id: every POST writes the body's value into ``live`` for that id and
echoes the *current* stored value back. Then, for arbitrary ids, arbitrary
target values (unicode, empty, HTML, very long), and a repeat count ``N`` in
``2..5``, we assert:

* every one of the ``N`` calls succeeds (no error is raised on repeat),
* the final ``live`` value equals the target value,
* every POST hit the SAME fixed resource id path — the set of written paths has
  size 1 and equals ``/wp-json/wp/v2/pages/{id}`` (or ``/media/{id}``), proving
  no duplicate resource was created,
* every call's returned model reflects the target value.
"""

from __future__ import annotations

import json

import httpx
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import SecretStr

from publishing_adapter import WordPressClient

BASE_URL = "https://example.com"
USERNAME = "editor"
APP_PASSWORD = SecretStr("abcd efgh ijkl mnop")


class _StatefulRecorder:
    """A stateful mock backend for the WordPress write endpoints.

    Tracks every request it handles and, for POSTs, mutates an in-memory
    ``live`` state keyed by resource id (``"pages/{id}"`` / ``"media/{id}"``).
    Each POST stores the written field value and echoes back the *current*
    stored value — modelling WordPress's "update the existing resource" POST
    semantics, so repeated same-value writes converge rather than duplicate.
    """

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.live: dict[str, str] = {}

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path
        body = json.loads(request.content) if request.content else {}
        if "/pages/" in path:
            key = path.rsplit("/wp-json/wp/v2/", 1)[-1]  # e.g. "pages/5"
            self.live[key] = body["content"]
            return httpx.Response(
                200, json={"id": 1, "content": {"rendered": self.live[key]}}
            )
        key = path.rsplit("/wp-json/wp/v2/", 1)[-1]  # e.g. "media/9"
        self.live[key] = body["alt_text"]
        return httpx.Response(200, json={"id": 1, "alt_text": self.live[key]})


def _make_client(recorder: _StatefulRecorder) -> WordPressClient:
    """Build a network-free client backed by the stateful recorder."""
    transport = httpx.MockTransport(recorder.handler)
    http_client = httpx.Client(transport=transport, base_url=BASE_URL)
    return WordPressClient(BASE_URL, USERNAME, APP_PASSWORD, client=http_client)


# --- Strategies --------------------------------------------------------------

_ids = st.integers(min_value=1, max_value=2**31 - 1)

# Repeat the same write between 2 and 5 times (the "more than once" case).
_repeat_counts = st.integers(min_value=2, max_value=5)

# Varied target values: empty, whitespace, unicode, HTML, and long strings.
_target_text = st.one_of(
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
            "<img src='x' alt='a cat'>",
            "café — naïve — 你好 — 😀",
            "A" * 5000,
            "line1\nline2\ttabbed",
        ]
    ),
)


# --- Property 31 -------------------------------------------------------------


@settings(max_examples=120)
@given(page_id=_ids, content=_target_text, times=_repeat_counts)
def test_property_31_repeated_page_write_is_idempotent(
    page_id: int, content: str, times: int
) -> None:
    """Applying the same page ``content`` write N times converges to the target
    with no duplicate resource and no error on repeat (Req 7.7)."""
    rec = _StatefulRecorder()
    client = _make_client(rec)

    expected_path = f"/wp-json/wp/v2/pages/{page_id}"

    results = []
    for _ in range(times):
        # Every repeated application must succeed — no error is raised.
        results.append(client.update_page_content(page_id, content))

    # Every call issued exactly one POST to the SAME fixed resource id — the
    # set of written paths has size 1 (no duplicate resource created).
    assert len(rec.requests) == times
    paths = {r.url.path for r in rec.requests}
    assert paths == {expected_path}
    assert all(r.method == "POST" for r in rec.requests)

    # Final live state equals the target value.
    assert rec.live == {f"pages/{page_id}": content}
    # Every returned model reflects the target value.
    assert all(page.content == content for page in results)


@settings(max_examples=120)
@given(media_id=_ids, alt_text=_target_text, times=_repeat_counts)
def test_property_31_repeated_media_write_is_idempotent(
    media_id: int, alt_text: str, times: int
) -> None:
    """Applying the same media ``alt_text`` write N times converges to the
    target with no duplicate resource and no error on repeat (Req 7.7)."""
    rec = _StatefulRecorder()
    client = _make_client(rec)

    expected_path = f"/wp-json/wp/v2/media/{media_id}"

    results = []
    for _ in range(times):
        results.append(client.update_media_alt_text(media_id, alt_text))

    assert len(rec.requests) == times
    paths = {r.url.path for r in rec.requests}
    assert paths == {expected_path}
    assert all(r.method == "POST" for r in rec.requests)

    assert rec.live == {f"media/{media_id}": alt_text}
    assert all(media.alt_text == alt_text for media in results)
