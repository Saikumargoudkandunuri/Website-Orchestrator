"""Anthropic Claude provider adapter (§5.2).

Claude's Messages API differs structurally from OpenAI's (``/v1/messages``,
``x-api-key`` + ``anthropic-version`` headers, ``system`` as a top-level field,
content returned as a list of blocks, ``usage.input_tokens``/``output_tokens``),
so this is a distinct adapter — proving the provider abstraction genuinely spans
different request/response shapes (§11.4). Injected ``httpx.Client`` keeps
contract tests network-free.
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

__all__ = ["ClaudeProvider"]

_DEFAULT_TIMEOUT_S = 30.0
_ANTHROPIC_VERSION = "2023-06-01"


class ClaudeProvider:
    provider_name = "claude"

    def __init__(
        self,
        api_key: SecretStr | str | None,
        model: str = "claude-3-5-sonnet-latest",
        *,
        base_url: str = "https://api.anthropic.com",
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
            "model": self._model,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "messages": [{"role": "user", "content": request.prompt}],
        }
        if request.system_prompt:
            body["system"] = request.system_prompt

        try:
            response = self._client.post(
                f"{self._base_url}/v1/messages", json=body, headers=self._headers()
            )
        except httpx.TimeoutException as exc:
            return Err(AIProviderError(f"claude request timed out ({type(exc).__name__})"))
        except httpx.HTTPError as exc:
            return Err(AIProviderError(f"claude request failed ({type(exc).__name__})"))

        if not response.is_success:
            return Err(AIProviderError(f"claude request failed with status {response.status_code}"))
        return self._parse(response)

    def name(self) -> str:
        return "claude"

    def supports_json_mode(self) -> bool:
        return False  # Claude uses prompt-guided JSON, not a strict json mode

    def _headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "anthropic-version": _ANTHROPIC_VERSION,
        }
        if self._api_key is not None and self._api_key.get_secret_value():
            headers["x-api-key"] = self._api_key.get_secret_value()
        return headers

    def _parse(
        self, response: httpx.Response
    ) -> Result[AICompletionResponse, AIProviderError]:
        try:
            payload = response.json()
            blocks = payload["content"]
            text = "".join(
                b.get("text", "") for b in blocks if b.get("type", "text") == "text"
            )
            finish = payload.get("stop_reason")
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            return Err(AIProviderError(f"claude response was not in the expected shape ({type(exc).__name__})"))
        usage_raw = payload.get("usage") or {}
        usage = TokenUsage(
            prompt_tokens=usage_raw.get("input_tokens"),
            completion_tokens=usage_raw.get("output_tokens"),
            total_tokens=(
                (usage_raw.get("input_tokens") or 0) + (usage_raw.get("output_tokens") or 0)
            )
            or None,
        )
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
        return f"ClaudeProvider(base_url={self._base_url!r}, model={self._model!r})"
