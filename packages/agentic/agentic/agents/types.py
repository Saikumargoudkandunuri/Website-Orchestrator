"""Shared typed models for multi-agent collaboration (M6 Build Phase F)."""
from __future__ import annotations

from typing import Protocol, TypeAlias

from pydantic import JsonValue

JsonPrimitive: TypeAlias = str | int | float | bool | None
JsonObject: TypeAlias = dict[str, JsonValue]


class SpecialistAgent(Protocol):
    """Reasoning-only specialist contract; agents never execute tools."""
    name: str
    capabilities: list[str]
    tools: list[str]
    skills: list[str]
    cost: float
    latency_ms: int
    risk: str
    confidence: float
    tenant_restrictions: list[str]
    approval_requirements: list[str]

    def reason(self, input_context: JsonObject) -> JsonObject:
        """Return typed reasoning evidence and runtime-safe proposals."""
        ...
