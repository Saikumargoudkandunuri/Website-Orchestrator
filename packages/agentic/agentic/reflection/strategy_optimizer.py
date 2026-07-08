"""Strategy Optimizer (M6 Build Phase E)."""
from __future__ import annotations

from typing import Any


class StrategyOptimizer:
    """Proposes workflow ordering and latency-minimizing strategies."""
    
    def optimize_strategy(self, tenant_id: str, summary: dict[str, Any]) -> dict[str, Any]:
        recommendations = []
        bottlenecks = summary.get("common_bottlenecks", [])
        
        # If any tool has repeated failures, recommend serialization or approval checks
        for bn in bottlenecks:
            tool = bn["tool"]
            failures = bn["failures"]
            if failures >= 2:
                recommendations.append({
                    "strategy": "serialize_and_approve",
                    "target_tool": tool,
                    "rationale": f"Tool '{tool}' failed {failures} times. Sequential gating advised.",
                })
                
        # Default optimization: parallelize independent nodes
        if not recommendations:
            recommendations.append({
                "strategy": "parallel_batching",
                "rationale": "No bottleneck tools identified. Maximize execution concurrency.",
            })
            
        return {
            "tenant_id": tenant_id,
            "recommendations": recommendations,
        }
