"""Simple in-memory TTL cache for AI responses."""
from __future__ import annotations

import time
from typing import Any, Dict, Optional


class TTLCache:
	def __init__(self) -> None:
		self.store: Dict[str, tuple[float, Any]] = {}

	def get(self, key: str) -> Optional[Any]:
		entry = self.store.get(key)
		if not entry:
			return None
		expires_at, value = entry
		if time.time() > expires_at:
			del self.store[key]
			return None
		return value

	def set(self, key: str, value: Any, ttl: int) -> None:
		self.store[key] = (time.time() + ttl, value)


_CACHE = TTLCache()


def cache_get(key: str) -> Optional[Any]:
	return _CACHE.get(key)


def cache_set(key: str, value: Any, ttl: int) -> None:
	_CACHE.set(key, value, ttl)
