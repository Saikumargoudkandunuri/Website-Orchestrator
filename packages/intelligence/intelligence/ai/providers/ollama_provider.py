"""Ollama provider adapter (§5.2).

Ollama's OpenAI-compatibility layer (``/v1/chat/completions``) lets us reuse the
OpenAI-compatible base. Local Ollama servers usually need no API key.
"""

from __future__ import annotations

import httpx
from pydantic import SecretStr

from intelligence.ai.providers.openai_provider import OpenAICompatibleProvider

__all__ = ["OllamaProvider"]


class OllamaProvider(OpenAICompatibleProvider):
    provider_name = "ollama"

    def __init__(
        self,
        model: str = "llama3",
        *,
        base_url: str = "http://localhost:11434/v1",
        api_key: SecretStr | str | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        super().__init__(base_url, model, api_key, client=client, name="ollama")
