"""Tests for agentic memory subsystem (M6 Build Phase C)."""
from __future__ import annotations

import time
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from brain.db import BrainBase
from agentic.goal.models import Goal, GoalContext, StructuredObjective
from agentic.memory.models import (
    ExperienceEpisode,
    GoalMemoryRecord,
    MemoryIndex,
    ReflectionLesson,
    SemanticFact,
    WorkflowTemplate,
)
from agentic.memory.repositories import (
    EpisodicMemoryRepository,
    GoalMemoryRepository,
    MemoryIndexRepository,
    ProceduralMemoryRepository,
    ReflectionMemoryRepository,
    SemanticMemoryRepository,
    EpisodeRecord,
    SemanticFactRecord,
    WorkflowTemplateRecord,
    ReflectionLessonRecord,
    GoalMemoryRecordRow,
    MemoryIndexRecord,
)
from agentic.memory.working_memory import WorkingMemory
from agentic.memory.episodic_memory import EpisodicMemory
from agentic.memory.semantic_memory import SemanticMemory
from agentic.memory.procedural_memory import ProceduralMemory
from agentic.memory.goal_memory import GoalMemory
from agentic.memory.reflection_memory import ReflectionMemory
from agentic.memory.knowledge_memory import KnowledgeMemory
from agentic.memory.memory_manager import MemoryManager
from agentic.memory.wiring import build_memory_container


@pytest.fixture
def db_session_factory():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # Register memory tables
    from agentic.memory.repositories import (
        EpisodeRecord,
        SemanticFactRecord,
        WorkflowTemplateRecord,
        ReflectionLessonRecord,
        GoalMemoryRecordRow,
        MemoryIndexRecord,
    )
    BrainBase.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def test_working_memory_lifecycle():
    wm = WorkingMemory()
    
    # 1. Set & Get
    wm.set("t1", "key1", "val1", ttl_seconds=1)
    assert wm.get("t1", "key1") == "val1"
    
    # 2. Tenant isolation
    assert wm.get("t2", "key1") is None
    
    # 3. Expiry
    time.sleep(1.1)
    assert wm.get("t1", "key1") is None


def test_memory_manager_lookups(db_session_factory):
    session = db_session_factory()
    
    # Build container
    container = build_memory_container(session, "tenant_1")
    manager = container.manager
    
    # 1. Semantic Memory check
    fact = SemanticFact(tenant_id="tenant_1", key="ai_model", value="gpt-4")
    container.semantic.save_fact(fact)
    
    assert manager.get_semantic_fact("ai_model") == "gpt-4"
    assert manager.get_semantic_fact("nonexistent") is None

    # 2. Episodic Memory check
    episode = ExperienceEpisode(
        tenant_id="tenant_1",
        site_id="site_123",
        actor="planner",
        success=True,
    )
    container.episodic.record_episode(episode)
    
    episodes = manager.find_relevant_experiences("site_123")
    assert len(episodes) == 1
    assert episodes[0].actor == "planner"
    
    # 3. Reflection Memory check
    lesson = ReflectionLesson(
        tenant_id="tenant_1",
        lesson="Technical fixes before content",
        confidence=0.9,
        evidence=["audit success"],
    )
    container.reflection.record_lesson(lesson)
    
    reflections = manager.find_relevant_reflections("technical")
    assert len(reflections) == 1
    assert reflections[0].confidence == 0.9
    
    # 4. Goal Memory check
    goal = Goal(
        id="goal_100",
        raw_objective="Improve organic traffic",
        context=GoalContext(tenant_id="tenant_1"),
    )
    record = GoalMemoryRecord(
        tenant_id="tenant_1",
        goal=goal,
        status="executing",
    )
    container.goal.save_goal_record(record)
    
    retrieved_goal = manager.get_goal_state("goal_100")
    assert retrieved_goal is not None
    assert retrieved_goal.status == "executing"
    
    # List active
    active = manager.list_active_goals()
    assert len(active) == 1
    assert active[0].goal.id == "goal_100"
