"""OpenRouter provider adapter (§5.2).

OpenRouter exposes an OpenAI-compatible Chat Completions API, so this is a thin
subclass of :class:`OpenAICompatibleProvider` differing only in default endpoint
and provider name.
"""

from __future__ import annotations

import httpx
from pydantic import SecretStr

from intelligence.ai.providers.openai_provider import OpenAICompatibleProvider

__all__ = ["OpenRouterProvider"]


class OpenRouterProvider(OpenAICompatibleProvider):
    provider_name = "openrouter"

    def __init__(
        self,
        api_key: SecretStr | str | None,
        model: str = "openrouter/auto",
        *,
        base_url: str = "https://openrouter.ai/api/v1",
        client: httpx.Client | None = None,
    ) -> None:
        super().__init__(base_url, model, api_key, client=client, name="openrouter")
