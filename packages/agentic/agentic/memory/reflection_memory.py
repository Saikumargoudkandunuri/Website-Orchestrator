"""Reflection Memory implementation (M6 Build Phase C)."""
from __future__ import annotations

from agentic.memory.models import ReflectionLesson
from agentic.memory.repositories import ReflectionMemoryRepository


class ReflectionMemory:
    """Stores lessons and observations generated from self-reflection."""
    
    def __init__(self, repository: ReflectionMemoryRepository) -> None:
        self._repo = repository
        
    def record_lesson(self, lesson: ReflectionLesson) -> None:
        """Store a lesson learned."""
        self._repo.save(lesson)
        
    def list_lessons(self, tenant_id: str) -> list[ReflectionLesson]:
        """Fetch all reflection lessons for a tenant."""
        return self._repo.get_all(tenant_id)
