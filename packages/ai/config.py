"""Configuration for AI Gateway loaded from environment variables."""
from __future__ import annotations

import os
from typing import Dict, List


def _env(key: str, default: str | None = None) -> str | None:
	return os.environ.get(key, default)


# Provider API keys (presence enables a provider)
PROVIDER_KEYS = {
	"google": _env("GOOGLE_API_KEY"),
	"groq": _env("GROQ_API_KEY"),
	"openrouter": _env("OPENROUTER_API_KEY"),
	"openai": _env("OPENAI_API_KEY"),
	"anthropic": _env("ANTHROPIC_API_KEY"),
	"together": _env("TOGETHER_API_KEY"),
	"huggingface": _env("HUGGINGFACE_API_KEY"),
	"cerebras": _env("CEREBRAS_API_KEY"),
	"mistral": _env("MISTRAL_API_KEY"),
	"deepseek": _env("DEEPSEEK_API_KEY"),
}

# Local provider URLs
OLLAMA_URL = _env("OLLAMA_URL")
LMSTUDIO_URL = _env("LMSTUDIO_URL")

# Gateway settings
AI_DEFAULT_MODEL = _env("AI_DEFAULT_MODEL") or "SMART_MODEL"
AI_FALLBACK_ENABLED = (_env("AI_FALLBACK_ENABLED") or "true").lower() in ("1", "true", "yes")
AI_MAX_RETRIES = int(_env("AI_MAX_RETRIES") or "3")
AI_REQUEST_TIMEOUT_SECONDS = int(_env("AI_REQUEST_TIMEOUT_SECONDS") or "30")
AI_CACHE_TTL_SECONDS = int(_env("AI_CACHE_TTL_SECONDS") or "300")
AI_PROVIDER_PRIORITY = [p.strip() for p in (_env("AI_PROVIDER_PRIORITY") or "google,openai,anthropic,groq").split(",") if p.strip()]


def is_provider_enabled(name: str) -> bool:
	key = PROVIDER_KEYS.get(name.lower())
	if key:
		return True
	# local providers by url
	if name.lower() == "ollama":
		return bool(OLLAMA_URL)
	if name.lower() == "lmstudio":
		return bool(LMSTUDIO_URL)
	return False


def enabled_providers() -> List[str]:
	return [name for name in PROVIDER_KEYS.keys() if is_provider_enabled(name)]
