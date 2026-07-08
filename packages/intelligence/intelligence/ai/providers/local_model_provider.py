"""Local model provider adapter (§5.2).

Covers self-hosted OpenAI-compatible inference servers (llama.cpp server, vLLM,
LM Studio, text-generation-webui's OpenAI extension, ...). It is the same
OpenAI-compatible wire format pointed at a local endpoint, so it reuses the base
adapter unchanged.
"""

from __future__ import annotations

import httpx
from pydantic import SecretStr

from intelligence.ai.providers.openai_provider import OpenAICompatibleProvider

__all__ = ["LocalModelProvider"]


class LocalModelProvider(OpenAICompatibleProvider):
    provider_name = "local"

    def __init__(
        self,
        model: str = "local-model",
        *,
        base_url: str = "http://localhost:8000/v1",
        api_key: SecretStr | str | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        super().__init__(base_url, model, api_key, client=client, name="local")
