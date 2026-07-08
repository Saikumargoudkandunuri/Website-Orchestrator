"""Goal Memory implementation (M6 Build Phase C)."""
from __future__ import annotations

from agentic.memory.models import GoalMemoryRecord
from agentic.memory.repositories import GoalMemoryRepository


class GoalMemory:
    """Tracks goal metrics, milestones, and deadlines across sessions."""
    
    def __init__(self, repository: GoalMemoryRepository) -> None:
        self._repo = repository
        
    def save_goal_record(self, record: GoalMemoryRecord) -> None:
        """Persist or update a goal memory record."""
        self._repo.save(record)
        
    def get_goal_record(self, tenant_id: str, goal_id: str) -> GoalMemoryRecord | None:
        """Fetch a goal memory record by goal ID."""
        return self._repo.get(tenant_id, goal_id)
        
    def list_goal_records(self, tenant_id: str) -> list[GoalMemoryRecord]:
        """Fetch all goal memory records for a tenant."""
        return self._repo.get_all(tenant_id)
