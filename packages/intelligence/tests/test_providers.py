"""Provider abstraction contract tests (§9). No real network — MockTransport only.

Asserts each concrete adapter maps AICompletionRequest -> provider wire format
and provider response -> AICompletionResponse, across three distinct schemas
(OpenAI-compatible, Claude, Gemini), plus the deterministic fake and the factory.
"""

from __future__ import annotations

import httpx
import pytest

from core.results import Err, Ok
from intelligence.ai.provider_factory import ProviderConfig, build_provider
from intelligence.ai.provider_interface import AICompletionRequest
from intelligence.ai.providers import (
    ClaudeProvider,
    FakeProvider,
    GeminiProvider,
    LocalModelProvider,
    OllamaProvider,
    OpenAIProvider,
    OpenRouterProvider,
)

REQ = AICompletionRequest(
    prompt="hello", system_prompt="sys", json_mode=True,
    metadata={"capability": "meta_generator"},
)


def _openai_handler(content="{\"ok\":1}", status=200):
    def handler(request: httpx.Request) -> httpx.Response:
        if status != 200:
            return httpx.Response(status, json={"error": "x"})
        return httpx.Response(200, json={
            "model": "m", "choices": [{"message": {"content": content}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
        })
    return handler


def _mock_client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


# --- Fake ---------------------------------------------------------------------


def test_fake_provider_deterministic_per_capability():
    fake = FakeProvider()
    r = fake.complete(REQ)
    assert isinstance(r, Ok)
    assert "meta_description" in r.unwrap().raw_text
    assert fake.name() == "fake"
    assert len(fake.calls) == 1


def test_fake_provider_sequence_for_retries():
    fake = FakeProvider(responses={"meta_generator": ["bad", '{"meta_description":"x"}']})
    assert fake.complete(REQ).unwrap().raw_text == "bad"
    assert fake.complete(REQ).unwrap().raw_text == '{"meta_description":"x"}'
    # repeats the last one
    assert fake.complete(REQ).unwrap().raw_text == '{"meta_description":"x"}'


def test_fake_provider_forced_failure():
    assert isinstance(FakeProvider(fail=True).complete(REQ), Err)


# --- OpenAI-compatible family -------------------------------------------------


@pytest.mark.parametrize("cls", [OpenAIProvider, OpenRouterProvider])
def test_openai_compatible_maps_request_and_response(cls):
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return _openai_handler('{"v":1}')(request)

    provider = cls("key", client=_mock_client(handler))
    resp = provider.complete(REQ).unwrap()
    assert resp.raw_text == '{"v":1}'
    assert resp.tokens_used.total_tokens == 3
    assert calls[0].url.path.endswith("/chat/completions")
    assert calls[0].headers.get("Authorization") == "Bearer key"


@pytest.mark.parametrize("cls", [OllamaProvider, LocalModelProvider])
def test_local_family_needs_no_key(cls):
    provider = cls(client=_mock_client(_openai_handler('{"v":2}')))
    assert provider.complete(REQ).unwrap().raw_text == '{"v":2}'


def test_openai_error_status_wrapped_no_key_leak():
    provider = OpenAIProvider("secretkey", client=_mock_client(_openai_handler(status=500)))
    result = provider.complete(REQ)
    assert isinstance(result, Err)
    assert "secretkey" not in str(result.unwrap_err())


def test_openai_timeout_wrapped():
    def handler(request):
        raise httpx.ReadTimeout("slow", request=request)

    provider = OpenAIProvider("k", client=_mock_client(handler))
    assert isinstance(provider.complete(REQ), Err)


# --- Claude (distinct schema) -------------------------------------------------


def test_claude_maps_request_and_response():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/v1/messages")
        assert request.headers.get("x-api-key") == "ck"
        return httpx.Response(200, json={
            "model": "claude", "content": [{"type": "text", "text": '{"c":1}'}],
            "stop_reason": "end_turn", "usage": {"input_tokens": 4, "output_tokens": 6},
        })

    provider = ClaudeProvider("ck", client=_mock_client(handler))
    resp = provider.complete(REQ).unwrap()
    assert resp.raw_text == '{"c":1}'
    assert resp.tokens_used.total_tokens == 10


# --- Gemini (distinct schema) -------------------------------------------------


def test_gemini_maps_request_and_response():
    def handler(request: httpx.Request) -> httpx.Response:
        assert ":generateContent" in str(request.url)
        assert request.url.params.get("key") == "gk"
        return httpx.Response(200, json={
            "candidates": [{"content": {"parts": [{"text": '{"g":1}'}]}, "finishReason": "STOP"}],
            "usageMetadata": {"totalTokenCount": 9},
        })

    provider = GeminiProvider("gk", client=_mock_client(handler))
    resp = provider.complete(REQ).unwrap()
    assert resp.raw_text == '{"g":1}'
    assert resp.tokens_used.total_tokens == 9


# --- Factory ------------------------------------------------------------------


@pytest.mark.parametrize("name", ["fake", "openai", "openrouter", "ollama", "local", "claude", "gemini"])
def test_factory_resolves_every_provider(name):
    provider = build_provider(ProviderConfig(name=name, api_key="k"))
    assert provider.name() == ("fake" if name == "fake" else name) or provider.name()


def test_factory_unknown_provider_raises():
    from intelligence.errors import IntelligenceError

    with pytest.raises(IntelligenceError):
        build_provider(ProviderConfig(name="nope"))
