"""In-memory usage tracking for providers."""
from __future__ import annotations

import threading
from decimal import Decimal
from typing import Dict


class ProviderUsage:
	def __init__(self) -> None:
		self.lock = threading.Lock()
		self.total_requests = 0
		self.input_tokens = 0
		self.output_tokens = 0
		self.estimated_cost = Decimal("0")
		self.total_latency_ms = 0
		self.error_count = 0

	def record(self, input_tokens: int, output_tokens: int, cost: Decimal, latency_ms: int, error: bool = False) -> None:
		with self.lock:
			self.total_requests += 1
			self.input_tokens += input_tokens
			self.output_tokens += output_tokens
			self.estimated_cost += cost
			self.total_latency_ms += latency_ms
			if error:
				self.error_count += 1

	def snapshot(self) -> Dict:
		with self.lock:
			avg_latency = (self.total_latency_ms / self.total_requests) if self.total_requests else 0
			success_rate = ((self.total_requests - self.error_count) / self.total_requests * 100) if self.total_requests else 100
			return {
				"total_requests": self.total_requests,
				"input_tokens": self.input_tokens,
				"output_tokens": self.output_tokens,
				"estimated_cost": float(self.estimated_cost),
				"avg_latency_ms": avg_latency,
				"error_count": self.error_count,
				"success_rate_percent": success_rate,
			}


_USAGE: Dict[str, ProviderUsage] = {}


def get_usage(provider: str) -> ProviderUsage:
	key = provider.lower()
	if key not in _USAGE:
		_USAGE[key] = ProviderUsage()
	return _USAGE[key]


def snapshot_all() -> Dict[str, Dict]:
	return {k: v.snapshot() for k, v in _USAGE.items()}
