"""Routing logic to select provider based on priority, health, latency, and rate limits."""
from __future__ import annotations

import asyncio
from typing import List, Optional, Tuple

from . import config
from .registry import get_registry


async def select_provider(preferred: Optional[List[str]] = None) -> Tuple[str, object]:
	"""Select a provider instance name and instance.

	Selection order: configured priority -> health -> simple round-robin by latency estimate.
	Returns (provider_name, provider_instance)
	"""
	registry = get_registry()
	if not registry:
		raise RuntimeError("No AI providers are enabled")
	order = preferred or config.AI_PROVIDER_PRIORITY
	# filter available providers in priority order
	for name in order:
		inst = registry.get(name.lower())
		if not inst:
			continue
		# attempt health check quickly
		try:
			health = await asyncio.wait_for(inst.health(), timeout=1.0)
		except Exception:
			health = "unavailable"
		if health != "healthy":
			continue
		# TODO: check rate limit/latency heuristics (simple pass-through)
		return name.lower(), inst
	# fallback: pick any healthy
	for name, inst in registry.items():
		try:
			if await asyncio.wait_for(inst.health(), timeout=1.0) == "healthy":
				return name, inst
		except Exception:
			continue
	# last resort: return first available
	name, inst = next(iter(registry.items()))
	return name, inst
