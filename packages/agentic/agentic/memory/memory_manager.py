"""Memory Manager core entrypoint (M6 Build Phase C)."""
from __future__ import annotations

from typing import Any

from agentic.memory.episodic_memory import EpisodicMemory
from agentic.memory.goal_memory import GoalMemory
from agentic.memory.knowledge_memory import KnowledgeMemory
from agentic.memory.models import (
    ExperienceEpisode,
    GoalMemoryRecord,
    ReflectionLesson,
    SemanticFact,
    WorkflowTemplate,
)
from agentic.memory.procedural_memory import ProceduralMemory
from agentic.memory.reflection_memory import ReflectionMemory
from agentic.memory.repositories import MemoryIndexRepository
from agentic.memory.semantic_memory import SemanticMemory
from agentic.memory.working_memory import WorkingMemory


class MemoryManager:
    """Single entrypoint coordinating all seven cognitive memory subsystems."""
    
    def __init__(
        self,
        tenant_id: str,
        working: WorkingMemory,
        episodic: EpisodicMemory,
        semantic: SemanticMemory,
        procedural: ProceduralMemory,
        goal: GoalMemory,
        reflection: ReflectionMemory,
        knowledge: KnowledgeMemory,
        index_repo: MemoryIndexRepository,
    ) -> None:
        self.tenant_id = tenant_id
        self.working = working
        self.episodic = episodic
        self.semantic = semantic
        self.procedural = procedural
        self.goal = goal
        self.reflection = reflection
        self.knowledge = knowledge
        self._index_repo = index_repo
        
    def get_working_context(self, key: str) -> Any | None:
        """Fetch auto-expiring context from Working Memory."""
        return self.working.get(self.tenant_id, key)
        
    def set_working_context(self, key: str, value: Any, ttl_seconds: int = 300) -> None:
        """Store auto-expiring context in Working Memory."""
        self.working.set(self.tenant_id, key, value, ttl_seconds)
        
    def find_relevant_experiences(self, site_id: str) -> list[ExperienceEpisode]:
        """Query Episodic Memory for relevant experiences matching the site."""
        episodes = self.episodic.list_episodes(self.tenant_id)
        return [e for e in episodes if e.site_id == site_id]
        
    def find_relevant_procedures(self, name_query: str) -> list[WorkflowTemplate]:
        """Query Procedural Memory for workflow templates by name filter."""
        # Simple procedural lookup (production would query by tags/names)
        template = self.procedural.get_template(self.tenant_id, name_query)
        return [template] if template else []
        
    def find_relevant_reflections(self, tag: str) -> list[ReflectionLesson]:
        """Query Reflection Memory for lessons associated with a tag/context."""
        lessons = self.reflection.list_lessons(self.tenant_id)
        # Filters lessons containing the tag query in lesson text or evidence list
        return [
            L for L in lessons
            if tag.lower() in L.lesson.lower() or any(tag.lower() in ev.lower() for ev in L.evidence)
        ]
        
    def get_semantic_fact(self, key: str) -> Any | None:
        """Query Semantic Memory for a business fact or preference."""
        fact = self.semantic.get_fact(self.tenant_id, key)
        return fact.value if fact else None
        
    def get_goal_state(self, goal_id: str) -> GoalMemoryRecord | None:
        """Query Goal Memory for a long-running objective state."""
        return self.goal.get_goal_record(self.tenant_id, goal_id)

    def list_active_goals(self) -> list[GoalMemoryRecord]:
        """List active/executing goals."""
        records = self.goal.list_goal_records(self.tenant_id)
        return [r for r in records if r.status in ("pending", "planning", "executing")]
