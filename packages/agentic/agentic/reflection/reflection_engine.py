"""Reflection Engine (M6 Build Phase E)."""
from __future__ import annotations

from typing import Any
import uuid

from agentic.memory.memory_manager import MemoryManager
from agentic.memory.models import ReflectionLesson
from agentic.reflection.repositories import ReflectionRepository


class ReflectionEngine:
    """Analyzes execution steps and writes reports/lessons to memory."""
    
    def __init__(self, repo: ReflectionRepository, memory_manager: MemoryManager) -> None:
        self._repo = repo
        self._memory_manager = memory_manager
        
    def reflect_on_execution(self, tenant_id: str, execution_id: str, steps: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Compile execution details into a ReflectionReport, then write lessons to ReflectionMemory.
        """
        total_steps = len(steps)
        successful_steps = sum(1 for s in steps if s.get("success", False))
        failed_steps = sum(1 for s in steps if not s.get("success", False))
        total_cost = sum(s.get("cost_dollars", 0.0) for s in steps)
        total_duration = sum(s.get("duration", 0.0) for s in steps)
        
        # Identify failed tools and providers
        failures = []
        for s in steps:
            if not s.get("success", False):
                failures.append({
                    "node_id": s.get("node_id"),
                    "tool": s.get("tool"),
                    "error": s.get("error", "Unknown error"),
                })
                
        report_id = str(uuid.uuid4())
        report = {
            "id": report_id,
            "execution_id": execution_id,
            "total_steps": total_steps,
            "successful_steps": successful_steps,
            "failed_steps": failed_steps,
            "total_cost": total_cost,
            "total_duration": total_duration,
            "failures": failures,
        }
        
        # Save locally in append-only DB
        self._repo.save(tenant_id, report_id, execution_id, report)
        
        # Write lesson to MemoryManager (Observation lesson)
        lesson_text = f"Execution {execution_id} completed. Successful steps: {successful_steps}/{total_steps}."
        if failed_steps > 0:
            lesson_text += f" Encountered {failed_steps} failures."
            
        lesson = ReflectionLesson(
            tenant_id=tenant_id,
            lesson=lesson_text,
            confidence=1.0,
            evidence=[f"steps_succeeded={successful_steps}", f"steps_failed={failed_steps}"],
            related_executions=[execution_id],
        )
        self._memory_manager.reflection.record_lesson(lesson)
        
        return report
