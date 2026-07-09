"""Typed exceptions for AI gateway."""
from __future__ import annotations

class AIError(Exception):
	pass


class ProviderError(AIError):
	pass


class ProviderUnavailableError(ProviderError):
	pass


class AuthError(ProviderError):
	pass


class RateLimitError(ProviderError):
	pass


class TimeoutError(ProviderError):
	pass
