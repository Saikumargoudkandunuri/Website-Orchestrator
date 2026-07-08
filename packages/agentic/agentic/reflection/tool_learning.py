"""Tool Learning tracking and scoring (M6 Build Phase E)."""
from __future__ import annotations

from typing import Any
from agentic.reflection.repositories import ToolScoreRepository


class ToolLearning:
    """Updates and retrieves tool quality weights."""
    
    def __init__(self, repo: ToolScoreRepository) -> None:
        self._repo = repo
        
    def record_tool_attempt(self, tenant_id: str, tool_name: str, success: bool, latency: float) -> None:
        """Record tool performance metrics traceably."""
        existing = self._repo.get_by_tool(tenant_id, tool_name)
        if existing:
            attempts = existing.get("attempts", 0) + 1
            successes = existing.get("successes", 0) + (1 if success else 0)
            avg_latency = (existing.get("avg_latency", 0.0) * (attempts - 1) + latency) / attempts
            success_rate = successes / attempts
        else:
            attempts = 1
            successes = 1 if success else 0
            avg_latency = latency
            success_rate = 1.0 if success else 0.0
            
        payload = {
            "tool_name": tool_name,
            "attempts": attempts,
            "successes": successes,
            "success_rate": success_rate,
            "avg_latency": avg_latency,
        }
        
        self._repo.save_score(
            tenant_id=tenant_id,
            tool_name=tool_name,
            success_rate=success_rate,
            avg_latency=avg_latency,
            payload=payload,
        )
        
    def get_tool_score(self, tenant_id: str, tool_name: str) -> float:
        """Return the calculated success rate factor for the tool (default 1.0)."""
        existing = self._repo.get_by_tool(tenant_id, tool_name)
        if existing:
            return float(existing.get("success_rate", 1.0))
        return 1.0
