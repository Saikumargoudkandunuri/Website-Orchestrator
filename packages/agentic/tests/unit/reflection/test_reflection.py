"""Tests for the reflection and learning subsystem (M6 Build Phase E)."""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from brain.db import BrainBase
from agentic.memory.wiring import build_memory_container
from agentic.memory.models import ExperienceEpisode
from agentic.reflection.wiring import build_reflection_container


@pytest.fixture
def db_session_factory():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # Register all tables
    from agentic.memory.repositories import (
        EpisodeRecord,
        SemanticFactRecord,
        WorkflowTemplateRecord,
        ReflectionLessonRecord,
        GoalMemoryRecordRow,
        MemoryIndexRecord,
    )
    from agentic.reflection.repositories import (
        ReflectionReportRecord,
        ProviderScoreRecord,
        ToolScoreRecord,
        ConfidenceCalibrationRecord,
    )
    BrainBase.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def test_reflection_and_lesson_creation(db_session_factory):
    session = db_session_factory()
    memory_container = build_memory_container(session, "tenant_1")
    reflection_container = build_reflection_container(session, "tenant_1", memory_container.manager)
    
    steps = [
        {"node_id": "step_1", "tool": "seo_audit", "success": True, "duration": 1.2, "cost_dollars": 0.1},
        {"node_id": "step_2", "tool": "content_generator", "success": False, "duration": 2.5, "cost_dollars": 0.5, "error": "Timeout"},
    ]
    
    # Run reflection
    report = reflection_container.reflection_engine.reflect_on_execution("tenant_1", "exec_1", steps)
    
    assert report["total_steps"] == 2
    assert report["successful_steps"] == 1
    assert report["failed_steps"] == 1
    assert len(report["failures"]) == 1
    assert report["failures"][0]["tool"] == "content_generator"
    
    # Check that lesson is written to Reflection Memory via MemoryManager
    lessons = memory_container.manager.find_relevant_reflections("exec_1")
    assert len(lessons) == 1
    assert "Encountered 1 failures" in lessons[0].lesson


def test_experience_analyzer_and_learning_engine(db_session_factory):
    session = db_session_factory()
    memory_container = build_memory_container(session, "tenant_1")
    reflection_container = build_reflection_container(session, "tenant_1", memory_container.manager)
    
    # Record mock episodes
    e1 = ExperienceEpisode(
        tenant_id="tenant_1",
        site_id="site_1",
        actor="user",
        success=True,
    )
    e2 = ExperienceEpisode(
        tenant_id="tenant_1",
        site_id="site_1",
        actor="user",
        success=False,
        actions=[{"action": "content_generator"}],
    )
    memory_container.episodic.record_episode(e1)
    memory_container.episodic.record_episode(e2)
    
    # Analyze experiences
    summary = reflection_container.experience_analyzer.analyze_experiences("tenant_1")
    assert summary["total_episodes"] == 2
    assert summary["overall_success_rate"] == 0.5
    assert len(summary["common_bottlenecks"]) == 1
    assert summary["common_bottlenecks"][0]["tool"] == "content_generator"
    
    # Learn from summary traceably
    learned = reflection_container.learning_engine.learn_from_summary("tenant_1", summary)
    assert len(learned["weights_updated"]) == 1
    assert learned["weights_updated"][0]["target"] == "tool:content_generator"
    assert learned["weights_updated"][0]["updated_value"] < 1.0


def test_provider_and_tool_scores(db_session_factory):
    session = db_session_factory()
    memory_container = build_memory_container(session, "tenant_1")
    reflection_container = build_reflection_container(session, "tenant_1", memory_container.manager)
    
    # Record provider attempts
    reflection_container.provider_learning.record_provider_attempt("tenant_1", "openai", success=True, latency=0.8)
    reflection_container.provider_learning.record_provider_attempt("tenant_1", "openai", success=False, latency=1.5)
    
    openai_score = reflection_container.provider_learning.get_provider_score("tenant_1", "openai")
    assert openai_score == 0.5
    
    # Record tool attempts
    reflection_container.tool_learning.record_tool_attempt("tenant_1", "seo_audit", success=True, latency=0.5)
    assert reflection_container.tool_learning.get_tool_score("tenant_1", "seo_audit") == 1.0


def test_confidence_calibration(db_session_factory):
    session = db_session_factory()
    memory_container = build_memory_container(session, "tenant_1")
    reflection_container = build_reflection_container(session, "tenant_1", memory_container.manager)
    
    # Calibration run
    res = reflection_container.confidence_engine.calibrate_category(
        tenant_id="tenant_1",
        category="technical_seo",
        predicted_success=0.90,
        actual_success=0.45,
    )
    # calibration factor = actual_avg / predicted_avg = 0.45 / 0.90 = 0.5
    assert res["calibration_factor"] == 0.5
    assert reflection_container.confidence_engine.get_calibration_factor("tenant_1", "technical_seo") == 0.5
