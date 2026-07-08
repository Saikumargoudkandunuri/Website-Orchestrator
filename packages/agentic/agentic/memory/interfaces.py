"""Interfaces/Protocols for the memory subsystem (M6 Build Phase C)."""
from __future__ import annotations

from typing import Any, Protocol

from agentic.goal.models import Goal
from agentic.planning.models import ExecutionGraph


class WorkingMemoryService(Protocol):
    """Protocol for short-lived, in-memory state."""
    
    def get(self, tenant_id: str, key: str) -> Any:
        ...
        
    def set(self, tenant_id: str, key: str, value: Any, ttl_seconds: int = 300) -> None:
        ...
        
    def delete(self, tenant_id: str, key: str) -> None:
        ...


class EpisodicMemoryService(Protocol):
    """Protocol for experience episodes."""
    
    def record_episode(self, tenant_id: str, episode_data: dict[str, Any]) -> None:
        ...
        
    def list_episodes(self, tenant_id: str) -> list[dict[str, Any]]:
        ...


class SemanticMemoryService(Protocol):
    """Protocol for business facts."""
    
    def get_fact(self, tenant_id: str, key: str) -> Any:
        ...
        
    def save_fact(self, tenant_id: str, key: str, value: Any) -> None:
        ...


class ProceduralMemoryService(Protocol):
    """Protocol for workflow templates."""
    
    def get_procedure(self, tenant_id: str, name: str) -> dict[str, Any] | None:
        ...
        
    def save_procedure(self, tenant_id: str, name: str, steps: list[dict[str, Any]]) -> None:
        ...


class GoalMemoryService(Protocol):
    """Protocol for long-running objectives."""
    
    def get_goal(self, tenant_id: str, goal_id: str) -> Goal | None:
        ...
        
    def save_goal(self, tenant_id: str, goal: Goal) -> None:
        ...
        
    def list_goals(self, tenant_id: str) -> list[Goal]:
        ...


class ReflectionMemoryService(Protocol):
    """Protocol for lessons learned."""
    
    def record_lesson(self, tenant_id: str, lesson: dict[str, Any]) -> None:
        ...
        
    def list_lessons(self, tenant_id: str) -> list[dict[str, Any]]:
        ...


class KnowledgeMemoryService(Protocol):
    """Protocol for indexing/referencing other knowledge layers."""
    
    def query_reference(self, tenant_id: str, ref_type: str, ref_id: str) -> dict[str, Any] | None:
        ...
