"""Concrete AIProvider adapters (§5.2).

One adapter per provider, each implementing the
:class:`~intelligence.ai.provider_interface.AIProvider` contract. Business code
never imports these directly — it depends on the interface and resolves a
concrete provider via :mod:`intelligence.ai.provider_factory`.
"""

from intelligence.ai.providers.claude_provider import ClaudeProvider
from intelligence.ai.providers.fake_provider import (
    DEFAULT_FAKE_RESPONSES,
    FakeProvider,
)
from intelligence.ai.providers.gemini_provider import GeminiProvider
from intelligence.ai.providers.local_model_provider import LocalModelProvider
from intelligence.ai.providers.ollama_provider import OllamaProvider
from intelligence.ai.providers.openai_provider import (
    OpenAICompatibleProvider,
    OpenAIProvider,
)
from intelligence.ai.providers.openrouter_provider import OpenRouterProvider

__all__ = [
    "ClaudeProvider",
    "FakeProvider",
    "DEFAULT_FAKE_RESPONSES",
    "GeminiProvider",
    "LocalModelProvider",
    "OllamaProvider",
    "OpenAICompatibleProvider",
    "OpenAIProvider",
    "OpenRouterProvider",
]
