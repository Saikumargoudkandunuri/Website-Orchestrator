"""Provider health monitoring helpers."""
from __future__ import annotations

import asyncio
from typing import Dict

from .registry import get_registry


_health: Dict[str, str] = {}


async def probe_provider(name: str, inst) -> None:
	try:
		status = await asyncio.wait_for(inst.health(), timeout=2.0)
	except Exception:
		status = "unavailable"
	_health[name.lower()] = status


async def probe_all() -> Dict[str, str]:
	registry = get_registry()
	tasks = [probe_provider(name, inst) for name, inst in registry.items()]
	await asyncio.gather(*tasks)
	return dict(_health)


def get_status(name: str) -> str:
	return _health.get(name.lower(), "disabled")
