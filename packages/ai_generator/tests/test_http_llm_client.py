"""Unit tests for :class:`HttpLLMClient` (Milestone 1).

The client is exercised against an injected :class:`httpx.MockTransport`, so its
request building, response parsing, single-attempt shape, and credential-safe
error wrapping are all verified without any network. This mirrors how the
Publishing_Adapter's WordPress client is tested.
"""

from __future__ import annotations

import httpx
import pytest

from ai_generator import HttpLLMClient
from core.exceptions import LLMUnavailableError


def _client(handler) -> HttpLLMClient:
    transport = httpx.MockTransport(handler)
    return HttpLLMClient(
        "https://llm.example/v1",
        "test-model",
        "super-secret-key",
        client=httpx.Client(transport=transport),
    )


def _chat_response(content: str) -> httpx.Response:
    return httpx.Response(
        200, json={"choices": [{"message": {"content": content}}]}
    )


def test_happy_path_returns_message_content() -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return _chat_response("A calm harbour at dusk")

    text = _client(handler).complete("describe it", system="be concise", max_output_tokens=32)
    assert text == "A calm harbour at dusk"
    # Exactly one attempt to the chat-completions endpoint, authenticated.
    assert len(calls) == 1
    req = calls[0]
    assert req.url.path.endswith("/chat/completions")
    assert req.headers.get("Authorization") == "Bearer super-secret-key"


def test_single_attempt_no_retry_on_500() -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(500, json={"error": "boom"})

    with pytest.raises(LLMUnavailableError):
        _client(handler).complete("x")
    assert len(calls) == 1  # no retry


def test_auth_error_wrapped_without_leaking_key() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "unauthorized"})

    with pytest.raises(LLMUnavailableError) as excinfo:
        _client(handler).complete("x")
    assert "super-secret-key" not in str(excinfo.value)


def test_timeout_wrapped_as_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(LLMUnavailableError):
        _client(handler).complete("x")


def test_transport_error_wrapped_as_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route", request=request)

    with pytest.raises(LLMUnavailableError):
        _client(handler).complete("x")


def test_malformed_body_wrapped_as_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": "shape"})

    with pytest.raises(LLMUnavailableError):
        _client(handler).complete("x")


def test_missing_base_url_raises_before_any_request() -> None:
    client = HttpLLMClient(None, "test-model", None)
    with pytest.raises(LLMUnavailableError):
        client.complete("x")


def test_repr_does_not_leak_key() -> None:
    client = HttpLLMClient("https://llm.example/v1", "m", "top-secret")
    assert "top-secret" not in repr(client)
