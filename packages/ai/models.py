"""Model alias registry mapping logical aliases to provider model names."""
from __future__ import annotations

from enum import Enum
from typing import Dict, Tuple


class ModelAlias(str, Enum):
	FAST_MODEL = "FAST_MODEL"
	SMART_MODEL = "SMART_MODEL"
	PREMIUM_MODEL = "PREMIUM_MODEL"
	LOCAL_MODEL = "LOCAL_MODEL"
	EMBEDDING_MODEL = "EMBEDDING_MODEL"
	VISION_MODEL = "VISION_MODEL"
	CODING_MODEL = "CODING_MODEL"


# Default mapping — can be changed via configuration in future
_ALIASES: Dict[ModelAlias, Tuple[str, str]] = {
	ModelAlias.FAST_MODEL: ("groq", "llama-3-8b"),
	ModelAlias.SMART_MODEL: ("google", "gemini-1.5-pro"),
	ModelAlias.PREMIUM_MODEL: ("openai", "gpt-4o"),
	ModelAlias.LOCAL_MODEL: ("ollama", "llama3"),
	ModelAlias.EMBEDDING_MODEL: ("openai", "text-embedding-3-small"),
	ModelAlias.VISION_MODEL: ("google", "gemini-1.5-flash"),
	ModelAlias.CODING_MODEL: ("anthropic", "claude-3-5-sonnet"),
}


def resolve(alias: ModelAlias) -> Tuple[str, str]:
	return _ALIASES[alias]


def available_aliases() -> Dict[str, Tuple[str, str]]:
	return {a.value: v for a, v in _ALIASES.items()}
