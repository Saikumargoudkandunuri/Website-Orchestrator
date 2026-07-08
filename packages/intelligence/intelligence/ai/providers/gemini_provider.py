"""Google Gemini provider adapter (§5.2).

Gemini's ``generateContent`` API differs again (``contents``/``parts`` payload,
``systemInstruction``, ``generationConfig``, API key as a query parameter,
``candidates[].content.parts[].text`` response, ``usageMetadata``), so it is a
third distinct adapter shape. Injected ``httpx.Client`` keeps tests network-free.
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

__all__ = ["GeminiProvider"]

_DEFAULT_TIMEOUT_S = 30.0


class GeminiProvider:
    provider_name = "gemini"

    def __init__(
        self,
        api_key: SecretStr | str | None,
        model: str = "gemini-1.5-flash",
        *,
        base_url: str = "https://generativelanguage.googleapis.com",
        client: httpx.Client | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._api_key = api_key if isinstance(api_key, SecretStr) else (
            SecretStr(api_key) if api_key is not None else None
        )
        self._owns_client = client is None
        self._client = client if client is not None else httpx.Client(
            timeout=_DEFAULT_TIMEOUT_S
        )

    def complete(
        self, request: AICompletionRequest
    ) -> Result[AICompletionResponse, AIProviderError]:
        body: dict[str, Any] = {
            "contents": [{"parts": [{"text": request.prompt}]}],
            "generationConfig": {
                "maxOutputTokens": request.max_tokens,
                "temperature": request.temperature,
            },
        }
        if request.system_prompt:
            body["systemInstruction"] = {"parts": [{"text": request.system_prompt}]}

        params = {}
        if self._api_key is not None and self._api_key.get_secret_value():
            params["key"] = self._api_key.get_secret_value()

        url = f"{self._base_url}/v1beta/models/{self._model}:generateContent"
        try:
            response = self._client.post(
                url, json=body, params=params, headers={"Content-Type": "application/json"}
            )
        except httpx.TimeoutException as exc:
            return Err(AIProviderError(f"gemini request timed out ({type(exc).__name__})"))
        except httpx.HTTPError as exc:
            return Err(AIProviderError(f"gemini request failed ({type(exc).__name__})"))

        if not response.is_success:
            return Err(AIProviderError(f"gemini request failed with status {response.status_code}"))
        return self._parse(response)

    def name(self) -> str:
        return "gemini"

    def supports_json_mode(self) -> bool:
        return True

    def _parse(
        self, response: httpx.Response
    ) -> Result[AICompletionResponse, AIProviderError]:
        try:
            payload = response.json()
            candidate = payload["candidates"][0]
            parts = candidate["content"]["parts"]
            text = "".join(p.get("text", "") for p in parts)
            finish = candidate.get("finishReason")
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            return Err(AIProviderError(f"gemini response was not in the expected shape ({type(exc).__name__})"))
        usage_raw = payload.get("usageMetadata") or {}
        usage = TokenUsage(
            prompt_tokens=usage_raw.get("promptTokenCount"),
            completion_tokens=usage_raw.get("candidatesTokenCount"),
            total_tokens=usage_raw.get("totalTokenCount"),
        )
        return Ok(
            AICompletionResponse(
                raw_text=text, tokens_used=usage, model=self._model, finish_reason=finish
            )
        )

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __repr__(self) -> str:  # pragma: no cover - credential-safe
        return f"GeminiProvider(base_url={self._base_url!r}, model={self._model!r})"
