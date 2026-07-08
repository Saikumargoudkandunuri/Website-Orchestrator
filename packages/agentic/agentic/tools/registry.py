"""Tool Registry for the Agent Runtime (M6 Build Phase A)."""
from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, Field

from agentic.goal.models import RiskLevel


class Capability(BaseModel):
    """A typed capability that a tool provides (e.g., 'rank_tracking', 'content_publish')."""
    domain: str
    action: str
    
    def matches(self, other: Capability) -> bool:
        """Returns True if this capability fulfills the requested capability."""
        return self.domain == other.domain and self.action == other.action


class ToolMetadata(BaseModel):
    """Metadata describing an orchestratable tool/service from M1-M5."""
    name: str
    capability: Capability
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    cost_estimate: float = 0.0
    requires_approval: bool = True
    risk_level: RiskLevel = RiskLevel.MEDIUM
    owning_package: str


class ToolRegistry(Protocol):
    """Registry holding all tools the Agent Runtime is permitted to orchestrate."""
    
    def register(self, metadata: ToolMetadata) -> None:
        """Register a new tool."""
        ...
        
    def get_by_name(self, name: str) -> ToolMetadata | None:
        """Fetch a specific tool by name."""
        ...
        
    def find_by_capability(self, capability: Capability) -> list[ToolMetadata]:
        """Find all tools matching a capability."""
        ...


class InMemoryToolRegistry(ToolRegistry):
    """In-memory implementation of ToolRegistry."""
    
    def __init__(self) -> None:
        self._tools: dict[str, ToolMetadata] = {}
        
    def register(self, metadata: ToolMetadata) -> None:
        self._tools[metadata.name] = metadata
        
    def get_by_name(self, name: str) -> ToolMetadata | None:
        return self._tools.get(name)
        
    def find_by_capability(self, capability: Capability) -> list[ToolMetadata]:
        return [
            tool for tool in self._tools.values()
            if tool.capability.matches(capability)
        ]


def build_default_tool_registry() -> ToolRegistry:
    """Pre-populate a ToolRegistry with default M1-M5 capabilities."""
    registry = InMemoryToolRegistry()
    
    registry.register(
        ToolMetadata(
            name="seo_audit",
            capability=Capability(domain="seo", action="technical_seo_audit"),
            input_schema={},
            output_schema={},
            cost_estimate=1.0,
            requires_approval=False,
            risk_level=RiskLevel.LOW,
            owning_package="engines",
        )
    )
    registry.register(
        ToolMetadata(
            name="content_generator",
            capability=Capability(domain="seo", action="content_generation"),
            input_schema={},
            output_schema={},
            cost_estimate=2.0,
            requires_approval=False,
            risk_level=RiskLevel.MEDIUM,
            owning_package="growth",
        )
    )
    registry.register(
        ToolMetadata(
            name="wp_publish",
            capability=Capability(domain="seo", action="publish"),
            input_schema={},
            output_schema={},
            cost_estimate=0.5,
            requires_approval=True,
            risk_level=RiskLevel.HIGH,
            owning_package="publishing_adapter",
        )
    )
    
    return registry

