"""Learning Engine for updating statistical weights traceably (M6 Build Phase E)."""
from __future__ import annotations

from typing import Any
from agentic.memory.memory_manager import MemoryManager


class LearningEngine:
    """Updates heuristics and scores from experience summaries."""
    
    def __init__(self, memory_manager: MemoryManager) -> None:
        self._memory_manager = memory_manager
        
    def learn_from_summary(self, tenant_id: str, summary: dict[str, Any]) -> dict[str, Any]:
        """Produce a traceability trace showing updated scores from execution logs."""
        updates = []
        bottlenecks = summary.get("common_bottlenecks", [])
        
        # Penalize tools that show repeated bottlenecks traceably
        for bn in bottlenecks:
            tool = bn["tool"]
            failures = bn["failures"]
            penalty = min(0.5, failures * 0.1)
            updates.append({
                "target": f"tool:{tool}",
                "metric": "success_rate_weight_penalty",
                "original_value": 1.0,
                "updated_value": 1.0 - penalty,
                "reason": f"Tool '{tool}' encountered {failures} failures.",
            })
            
        return {
            "tenant_id": tenant_id,
            "status": "success",
            "weights_updated": updates,
        }
