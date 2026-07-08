"""Tool Selector (M6 Build Phase A)."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from agentic.goal.models import Goal, RiskLevel
from agentic.tools.registry import Capability, ToolMetadata, ToolRegistry


class ExecutionPolicy(BaseModel):
    """Tenant-configured execution preferences for the Agent Runtime."""
    tenant_id: str
    max_tool_cost_dollars: float | None = None
    allowed_risk_level: RiskLevel = RiskLevel.CRITICAL
    preferred_providers: list[str] = []


class ToolSelector:
    """Selects and filters tools from the registry for a specific step."""
    
    def __init__(self, registry: ToolRegistry) -> None:
        self._registry = registry
        
    def select(
        self, goal: Goal, required_capability: Capability, policy: ExecutionPolicy | None = None
    ) -> list[ToolMetadata]:
        """
        Find candidate tools for a required capability, filtered by goal constraints
        and tenant execution policy.
        """
        candidates = self._registry.find_by_capability(required_capability)
        
        # Filter by Goal Constraints (budget)
        if goal.constraints.max_budget_dollars is not None:
            candidates = [
                c for c in candidates 
                if c.cost_estimate <= goal.constraints.max_budget_dollars
            ]
            
        # Filter by Tenant Execution Policy
        if policy:
            if policy.max_tool_cost_dollars is not None:
                candidates = [
                    c for c in candidates 
                    if c.cost_estimate <= policy.max_tool_cost_dollars
                ]
            
            # (Additional policy filtering like preferred_providers could go here)
            
        return candidates
