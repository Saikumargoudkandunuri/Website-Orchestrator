"""API integration tests for cognitive memory."""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from brain.db import BrainBase
from api.app import create_app
from agentic.goal.models import Goal, GoalContext, StructuredObjective
from agentic.memory.models import GoalMemoryRecord, ReflectionLesson
from agentic.memory.wiring import build_memory_container


@pytest.fixture
def app_with_memory():
    # SQLite in-memory DB
    from sqlalchemy.pool import StaticPool
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # Register ORM rows
    from agentic.memory.repositories import (
        EpisodeRecord,
        SemanticFactRecord,
        WorkflowTemplateRecord,
        ReflectionLessonRecord,
        GoalMemoryRecordRow,
        MemoryIndexRecord,
    )
    BrainBase.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    
    container = build_memory_container(session_factory, "tenant_1")
    
    # Pre-populate a Goal
    goal = Goal(
        id="goal_10",
        raw_objective="Improve organic traffic",
        structured_objective=StructuredObjective(
            target_metric="organic_traffic",
            magnitude="25",
            timeframe_days=30,
            target_site_id="site_1",
        ),
        context=GoalContext(tenant_id="tenant_1"),
    )
    record = GoalMemoryRecord(
        tenant_id="tenant_1",
        goal=goal,
        status="executing",
    )
    container.goal.save_goal_record(record)
    
    # Create the app manually injecting subsystems
    from unittest.mock import MagicMock
    app = create_app(
        crawler=MagicMock(),
        digital_twin=MagicMock(),
        check_engine=MagicMock(),
        fix_generator=MagicMock(),
        governance=MagicMock(),
        tenant_id="tenant_1",
        agentic_memory=container,
    )
    
    return app


def test_memory_api_endpoints(app_with_memory):
    client = TestClient(app_with_memory)
    
    # 1. GET /agentic/memory/goals
    res = client.get("/agentic/memory/goals")
    assert res.status_code == 200
    goals = res.json()
    assert len(goals) == 1
    assert goals[0]["goal"]["id"] == "goal_10"
    
    # 2. GET /agentic/memory/goals/{id}
    res = client.get("/agentic/memory/goals/goal_10")
    assert res.status_code == 200
    assert res.json()["status"] == "executing"
    
    # 3. POST /agentic/memory/reflections
    lesson_data = {
        "lesson": "Caching speed is high",
        "confidence": 0.85,
        "evidence": ["page speed audit"],
    }
    res = client.post("/agentic/memory/reflections", json=lesson_data)
    assert res.status_code == 200
    assert res.json()["lesson"] == "Caching speed is high"
    
    # 4. GET /agentic/memory/reflections
    res = client.get("/agentic/memory/reflections")
    assert res.status_code == 200
    assert len(res.json()) == 1
    assert res.json()[0]["lesson"] == "Caching speed is high"
    
    # 5. GET /agentic/memory/search
    res = client.get("/agentic/memory/search?query=Caching")
    assert res.status_code == 200
    assert len(res.json()) == 1
