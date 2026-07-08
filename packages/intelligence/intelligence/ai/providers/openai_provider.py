"""OpenAI (and OpenAI-compatible) provider adapters (§5.2).

The OpenAI Chat Completions schema is shared by several providers (OpenRouter,
Ollama, and most local servers), so :class:`OpenAICompatibleProvider` holds the
common request/response mapping and the credential-safe, single-attempt HTTP
pipeline, and the concrete adapters are thin subclasses differing only by
default endpoint, provider name, and auth style.

Every adapter accepts an injected :class:`httpx.Client` so contract tests run
against :class:`httpx.MockTransport` with no network, and wraps every failure
into a typed :class:`~intelligence.errors.AIProviderError` returned as
:class:`~core.results.Err` — never raised, never leaking the API key.
"""

from __future__ import annotations

from typing import Any

import httpx
from pydantic import SecretStr

from core.results import Err, Ok, Result
from intelligence.ai.provider_interface import (
    AICompletionRequest,
    AICompletionResponse,
)
from intelligence.errors import AIProviderError
from intelligence.models.ai_invocation import TokenUsage

__all__ = ["OpenAICompatibleProvider", "OpenAIProvider"]

_DEFAULT_TIMEOUT_S = 30.0


def _coerce_secret(key: SecretStr | str | None) -> SecretStr | None:
    if key is None:
        return None
    return key if isinstance(key, SecretStr) else SecretStr(key)


class OpenAICompatibleProvider:
    """Base adapter for any OpenAI Chat-Completions-compatible endpoint."""

    provider_name = "openai_compatible"

    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: SecretStr | str | None = None,
        *,
        client: httpx.Client | None = None,
        name: str | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._api_key = _coerce_secret(api_key)
        self._owns_client = client is None
        self._client = client if client is not None else httpx.Client(
            timeout=_DEFAULT_TIMEOUT_S
        )
        self._name = name or self.provider_name

    # --- AIProvider ----------------------------------------------------------

    def complete(
        self, request: AICompletionRequest
    ) -> Result[AICompletionResponse, AIProviderError]:
        messages: list[dict[str, str]] = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.append({"role": "user", "content": request.prompt})

        body: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
        }
        if request.json_mode and self.supports_json_mode():
            body["response_format"] = {"type": "json_object"}

        try:
            response = self._client.post(
                f"{self._base_url}/chat/completions",
                json=body,
                headers=self._headers(),
            )
        except httpx.TimeoutException as exc:
            return Err(AIProviderError(f"{self._name} request timed out ({type(exc).__name__})"))
        except httpx.HTTPError as exc:
            return Err(AIProviderError(f"{self._name} request failed ({type(exc).__name__})"))

        if not response.is_success:
            return Err(
                AIProviderError(
                    f"{self._name} request failed with status {response.status_code}"
                )
            )
        return self._parse(response)

    def name(self) -> str:
        return self._name

    def supports_json_mode(self) -> bool:
        return True

    # --- Helpers -------------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._api_key is not None and self._api_key.get_secret_value():
            headers["Authorization"] = f"Bearer {self._api_key.get_secret_value()}"
        return headers

    def _parse(
        self, response: httpx.Response
    ) -> Result[AICompletionResponse, AIProviderError]:
        try:
            payload = response.json()
            choice = payload["choices"][0]
            text = choice["message"]["content"]
            finish = choice.get("finish_reason")
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            return Err(
                AIProviderError(
                    f"{self._name} response was not in the expected shape "
                    f"({type(exc).__name__})"
                )
            )
        if not isinstance(text, str):
            return Err(AIProviderError(f"{self._name} response content was not text"))
        usage = _openai_usage(payload.get("usage"))
        return Ok(
            AICompletionResponse(
                raw_text=text,
                tokens_used=usage,
                model=payload.get("model", self._model),
                finish_reason=finish,
            )
        )

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __repr__(self) -> str:  # pragma: no cover - credential-safe
        return f"{type(self).__name__}(base_url={self._base_url!r}, model={self._model!r})"


def _openai_usage(usage: Any) -> TokenUsage | None:
    if not isinstance(usage, dict):
        return None
    return TokenUsage(
        prompt_tokens=usage.get("prompt_tokens"),
        completion_tokens=usage.get("completion_tokens"),
        total_tokens=usage.get("total_tokens"),
    )


class OpenAIProvider(OpenAICompatibleProvider):
    """The OpenAI provider adapter (§5.2)."""

    provider_name = "openai"

    def __init__(
        self,
        api_key: SecretStr | str | None,
        model: str = "gpt-4o-mini",
        *,
        base_url: str = "https://api.openai.com/v1",
        client: httpx.Client | None = None,
    ) -> None:
        super().__init__(base_url, model, api_key, client=client, name="openai")
