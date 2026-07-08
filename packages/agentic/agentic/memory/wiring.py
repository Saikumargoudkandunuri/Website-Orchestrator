"""Dependency Injection wiring for the memory subsystem (M6 Build Phase C)."""
from __future__ import annotations

from dataclasses import dataclass
from sqlalchemy.orm import Session, sessionmaker

from brain.decision.repositories import DecisionRepository, HistoricalOutcomeRepository
from brain.repositories import KnowledgeGraphRepository, SiteSynthesisRepository
from intelligence.repositories.ai_invocation_repository import AIInvocationRepository
from intelligence.repositories.knowledge_object_repository import KnowledgeObjectRepository

from agentic.memory.episodic_memory import EpisodicMemory
from agentic.memory.goal_memory import GoalMemory
from agentic.memory.knowledge_memory import KnowledgeMemory
from agentic.memory.memory_manager import MemoryManager
from agentic.memory.procedural_memory import ProceduralMemory
from agentic.memory.reflection_memory import ReflectionMemory
from agentic.memory.repositories import (
    EpisodicMemoryRepository,
    GoalMemoryRepository,
    MemoryIndexRepository,
    ProceduralMemoryRepository,
    ReflectionMemoryRepository,
    SemanticMemoryRepository,
)
from agentic.memory.semantic_memory import SemanticMemory
from agentic.memory.working_memory import WorkingMemory


@dataclass
class MemoryContainer:
    """Memory-layer repositories, services, and manager."""
    tenant_id: str
    working: WorkingMemory
    episodic_repo: EpisodicMemoryRepository
    semantic_repo: SemanticMemoryRepository
    procedural_repo: ProceduralMemoryRepository
    goal_repo: GoalMemoryRepository
    reflection_repo: ReflectionMemoryRepository
    index_repo: MemoryIndexRepository
    
    episodic: EpisodicMemory
    semantic: SemanticMemory
    procedural: ProceduralMemory
    goal: GoalMemory
    reflection: ReflectionMemory
    knowledge: KnowledgeMemory
    
    manager: MemoryManager


def build_memory_container(
    session_source: Session | sessionmaker[Session] | object,
    tenant_id: str,
    *,
    ko_repo: KnowledgeObjectRepository | None = None,
    kg_repo: KnowledgeGraphRepository | None = None,
    decision_repo: DecisionRepository | None = None,
    synthesis_repo: SiteSynthesisRepository | None = None,
    historical_repo: HistoricalOutcomeRepository | None = None,
    ai_invocation_repo: AIInvocationRepository | None = None,
) -> MemoryContainer:
    """Wire up the repositories, services, and manager for Cognitive Memory."""
    
    # 1. Instantiate Repositories
    episodic_repo = EpisodicMemoryRepository(session_source, tenant_id=tenant_id)
    semantic_repo = SemanticMemoryRepository(session_source, tenant_id=tenant_id)
    procedural_repo = ProceduralMemoryRepository(session_source, tenant_id=tenant_id)
    goal_repo = GoalMemoryRepository(session_source, tenant_id=tenant_id)
    reflection_repo = ReflectionMemoryRepository(session_source, tenant_id=tenant_id)
    index_repo = MemoryIndexRepository(session_source, tenant_id=tenant_id)
    
    # 2. Instantiate Subsystems
    working = WorkingMemory()
    episodic = EpisodicMemory(episodic_repo)
    semantic = SemanticMemory(semantic_repo)
    procedural = ProceduralMemory(procedural_repo)
    goal = GoalMemory(goal_repo)
    reflection = ReflectionMemory(reflection_repo)
    
    knowledge = KnowledgeMemory(
        ko_repo=ko_repo,
        kg_repo=kg_repo,
        decision_repo=decision_repo,
        synthesis_repo=synthesis_repo,
        historical_repo=historical_repo,
        ai_invocation_repo=ai_invocation_repo,
    )
    
    # 3. Instantiate Coordinator (Memory Manager)
    manager = MemoryManager(
        tenant_id=tenant_id,
        working=working,
        episodic=episodic,
        semantic=semantic,
        procedural=procedural,
        goal=goal,
        reflection=reflection,
        knowledge=knowledge,
        index_repo=index_repo,
    )
    
    return MemoryContainer(
        tenant_id=tenant_id,
        working=working,
        episodic_repo=episodic_repo,
        semantic_repo=semantic_repo,
        procedural_repo=procedural_repo,
        goal_repo=goal_repo,
        reflection_repo=reflection_repo,
        index_repo=index_repo,
        episodic=episodic,
        semantic=semantic,
        procedural=procedural,
        goal=goal,
        reflection=reflection,
        knowledge=knowledge,
        manager=manager,
    )
