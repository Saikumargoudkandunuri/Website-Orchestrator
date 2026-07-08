"""Configuration-driven AI provider resolution (§5.2).

The single place that maps a configured provider *name* to a concrete adapter.
No business code imports a concrete provider; it calls :func:`build_provider`
(or is handed an :class:`~intelligence.ai.provider_interface.AIProvider` via DI),
so switching providers is a configuration change, never a code change.

Selection is driven by a :class:`ProviderConfig` (populated from env/config by
the composition root), keeping this module free of global state and hidden
singletons.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import httpx
from pydantic import SecretStr

from intelligence.ai.provider_interface import AIProvider
from intelligence.ai.providers import (
    ClaudeProvider,
    FakeProvider,
    GeminiProvider,
    LocalModelProvider,
    OllamaProvider,
    OpenAIProvider,
    OpenRouterProvider,
)
from intelligence.errors import IntelligenceError

__all__ = ["ProviderConfig", "build_provider", "SUPPORTED_PROVIDERS"]

#: Provider names this factory can resolve.
SUPPORTED_PROVIDERS: tuple[str, ...] = (
    "fake",
    "openai",
    "openrouter",
    "ollama",
    "local",
    "claude",
    "gemini",
)


@dataclass(frozen=True)
class ProviderConfig:
    """Provider selection + connection settings (from env/config)."""

    name: str = "fake"
    model: str | None = None
    api_key: SecretStr | str | None = None
    base_url: str | None = None
    #: Optional canned responses for the fake provider (tests/offline).
    fake_responses: dict[str, str] = field(default_factory=dict)


def build_provider(
    config: ProviderConfig, *, client: httpx.Client | None = None
) -> AIProvider:
    """Resolve a concrete :class:`AIProvider` from ``config``.

    ``client`` (an injected :class:`httpx.Client`) lets tests supply a
    :class:`httpx.MockTransport`; production omits it and each adapter creates
    its own timeout-bound client.
    """
    name = (config.name or "fake").strip().lower()
    if name == "fake":
        return FakeProvider(responses=dict(config.fake_responses))
    if name == "openai":
        return OpenAIProvider(
            config.api_key,
            _model(config, "gpt-4o-mini"),
            **_url_kw(config),
            client=client,
        )
    if name == "openrouter":
        return OpenRouterProvider(
            config.api_key,
            _model(config, "openrouter/auto"),
            **_url_kw(config),
            client=client,
        )
    if name == "ollama":
        return OllamaProvider(
            _model(config, "llama3"),
            api_key=config.api_key,
            **_url_kw(config),
            client=client,
        )
    if name == "local":
        return LocalModelProvider(
            _model(config, "local-model"),
            api_key=config.api_key,
            **_url_kw(config),
            client=client,
        )
    if name == "claude":
        return ClaudeProvider(
            config.api_key,
            _model(config, "claude-3-5-sonnet-latest"),
            **_url_kw(config),
            client=client,
        )
    if name == "gemini":
        return GeminiProvider(
            config.api_key,
            _model(config, "gemini-1.5-flash"),
            **_url_kw(config),
            client=client,
        )
    raise IntelligenceError(
        f"Unknown AI provider {config.name!r}; supported: {', '.join(SUPPORTED_PROVIDERS)}"
    )


def _model(config: ProviderConfig, default: str) -> str:
    return config.model or default


def _url_kw(config: ProviderConfig) -> dict[str, str]:
    """Pass ``base_url`` through only when configured (else adapter default)."""
    return {"base_url": config.base_url} if config.base_url else {}
