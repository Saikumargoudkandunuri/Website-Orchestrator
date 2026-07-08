"""Experience Analyzer (M6 Build Phase E)."""
from __future__ import annotations

from typing import Any
from agentic.memory.memory_manager import MemoryManager


class ExperienceAnalyzer:
    """Aggregates execution metrics across multiple episodes."""
    
    def __init__(self, memory_manager: MemoryManager) -> None:
        self._memory_manager = memory_manager
        
    def analyze_experiences(self, tenant_id: str) -> dict[str, Any]:
        """Aggregate histories to produce an ExperienceSummary."""
        episodes = self._memory_manager.episodic.list_episodes(tenant_id)
        total_episodes = len(episodes)
        if not episodes:
            return {
                "total_episodes": 0,
                "overall_success_rate": 1.0,
                "common_bottlenecks": [],
            }
            
        success_count = sum(1 for e in episodes if e.success)
        overall_success_rate = success_count / total_episodes
        
        # Aggregate tools and failure counts
        tool_failure_counts: dict[str, int] = {}
        for e in episodes:
            if not e.success:
                # Count transient/permanent errors in actions
                for act in e.actions:
                    tool_name = act.get("action", "unknown_tool")
                    tool_failure_counts[tool_name] = tool_failure_counts.get(tool_name, 0) + 1
                    
        # Identify common bottlenecks
        bottlenecks = [
            {"tool": tool, "failures": count}
            for tool, count in sorted(tool_failure_counts.items(), key=lambda x: x[1], reverse=True)
        ]
        
        return {
            "total_episodes": total_episodes,
            "overall_success_rate": overall_success_rate,
            "common_bottlenecks": bottlenecks,
        }
