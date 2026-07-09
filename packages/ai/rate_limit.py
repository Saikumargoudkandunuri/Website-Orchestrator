"""Simple per-provider token-bucket rate limiter (in-memory)."""
from __future__ import annotations

import time
import threading
from typing import Dict


class TokenBucket:
	def __init__(self, capacity: int, refill_per_sec: float) -> None:
		self.capacity = capacity
		self.tokens = capacity
		self.refill_per_sec = refill_per_sec
		self.last = time.time()
		self.lock = threading.Lock()

	def consume(self, tokens: int = 1) -> bool:
		with self.lock:
			now = time.time()
			elapsed = now - self.last
			self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_per_sec)
			self.last = now
			if self.tokens >= tokens:
				self.tokens -= tokens
				return True
			return False


_BUCKETS: Dict[str, TokenBucket] = {}


def get_bucket(provider: str) -> TokenBucket:
	key = provider.lower()
	if key not in _BUCKETS:
		# default small bursty allowance
		_BUCKETS[key] = TokenBucket(capacity=100, refill_per_sec=1)
	return _BUCKETS[key]


def allow(provider: str, tokens: int = 1) -> bool:
	return get_bucket(provider).consume(tokens)
