"""API integration tests for the multi-agent platform."""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from brain.db import BrainBase
from api.app import create_app
from agentic.memory.wiring import build_memory_container
from agentic.runtime.wiring import build_runtime_container
from agentic.tools.registry import build_default_tool_registry
from agentic.agents.wiring import build_agent_container


@pytest.fixture
def app_with_agents():
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
    from agentic.runtime.repositories import (
        CheckpointRecord,
        ExecutionRecordRow,
        ExecutionMetricsRecord,
    )
    from agentic.reflection.repositories import (
        ReflectionReportRecord,
        ProviderScoreRecord,
        ToolScoreRecord,
        ConfidenceCalibrationRecord,
    )
    from agentic.agents.repositories import (
        MissionRecord,
        BlackboardEntryRecord,
        MessageRecord,
    )
    BrainBase.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    
    memory_container = build_memory_container(session_factory, "tenant_1")
    registry = build_default_tool_registry()
    runtime_container = build_runtime_container(session_factory, "tenant_1", registry, memory_container.manager)
    agent_container = build_agent_container(session_factory, "tenant_1", runtime_container.runtime)
    
    # Create the app manually injecting subsystems
    from unittest.mock import MagicMock
    app = create_app(
        crawler=MagicMock(),
        digital_twin=MagicMock(),
        check_engine=MagicMock(),
        fix_generator=MagicMock(),
        governance=MagicMock(),
        tenant_id="tenant_1",
        agentic_memory=memory_container,
        agentic_runtime=runtime_container,
        agentic_agents=agent_container,
    )
    
    return app


def test_agent_api_endpoints(app_with_agents):
    client = TestClient(app_with_agents)
    
    # 1. POST /agentic/missions
    res = client.post("/agentic/missions?goal_id=goal_99&objective=Improve organic rank by 30%")
    assert res.status_code == 200
    mission_id = res.json()["mission_id"]
    assert mission_id.startswith("msn_")
    
    # 2. GET /agentic/missions/{id}
    res = client.get(f"/agentic/missions/{mission_id}")
    assert res.status_code == 200
    assert res.json()["state"] == "completed"
    
    # 3. GET /agentic/missions/{id}/agents
    res = client.get(f"/agentic/missions/{mission_id}/agents")
    assert res.status_code == 200
    assert len(res.json()) > 0
    
    # 4. GET /agentic/missions/{id}/blackboard
    res = client.get(f"/agentic/missions/{mission_id}/blackboard")
    assert res.status_code == 200
    assert len(res.json()) > 0
    
    # 5. GET /agentic/missions/{id}/messages
    res = client.get(f"/agentic/missions/{mission_id}/messages")
    assert res.status_code == 200
    assert len(res.json()) > 0
