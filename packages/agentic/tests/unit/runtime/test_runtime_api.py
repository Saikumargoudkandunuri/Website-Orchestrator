"""API integration tests for agentic runtime."""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from brain.db import BrainBase
from api.app import create_app
from agentic.goal.models import RiskLevel
from agentic.planning.models import ExecutionGraph, ExecutionNode
from agentic.tools.registry import build_default_tool_registry
from agentic.memory.wiring import build_memory_container
from agentic.runtime.wiring import build_runtime_container


@pytest.fixture
def app_with_runtime():
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
    from agentic.runtime.repositories import (
        CheckpointRecord,
        ExecutionRecordRow,
        ExecutionMetricsRecord,
    )
    BrainBase.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    
    memory_container = build_memory_container(session_factory, "tenant_1")
    registry = build_default_tool_registry()
    runtime_container = build_runtime_container(
        session_factory,
        "tenant_1",
        registry=registry,
        memory_manager=memory_container.manager,
    )
    
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
    )
    
    return app


def test_runtime_api_endpoints(app_with_runtime):
    client = TestClient(app_with_runtime)
    
    # Prepare mock graph
    node = ExecutionNode(
        id="n_audit",
        goal_id="goal_test",
        action_type="seo_audit",
        risk_level=RiskLevel.LOW,
    )
    graph = ExecutionGraph(
        nodes={"n_audit": node},
        edges=[],
    )
    plan_payload = {
        "goal_id": "goal_test",
        "graph": graph.model_dump(mode="json"),
    }
    
    # 1. POST /agentic/runtime/start
    res = client.post("/agentic/runtime/start?execution_id=exec_10", json=plan_payload)
    assert res.status_code == 200
    assert res.json()["state"] == "ready"
    
    # 2. POST /agentic/runtime/step
    res = client.post("/agentic/runtime/step?execution_id=exec_10")
    assert res.status_code == 200
    assert res.json()["state"] == "ready"
    assert res.json()["executed_node"] == "n_audit"
    
    # 3. GET /agentic/runtime/{id}
    res = client.get("/agentic/runtime/exec_10")
    assert res.status_code == 200
    assert res.json()["state"] in ("ready", "running")
    
    # 4. GET /agentic/runtime/{id}/checkpoint
    res = client.get("/agentic/runtime/exec_10/checkpoint")
    assert res.status_code == 200
    assert "n_audit" in res.json()["completed_node_ids"]
