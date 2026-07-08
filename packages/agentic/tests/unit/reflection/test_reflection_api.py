"""API integration tests for reflection and learning."""
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
from agentic.reflection.wiring import build_reflection_container


@pytest.fixture
def app_with_reflection():
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
    session_factory = sessionmaker(bind=engine)
    
    memory_container = build_memory_container(session_factory, "tenant_1")
    reflection_container = build_reflection_container(
        session_factory,
        "tenant_1",
        memory_manager=memory_container.manager,
    )
    
    # Save a mock provider score and calibration to verify API GET routes
    reflection_container.provider_learning.record_provider_attempt("tenant_1", "mock_prov", success=True, latency=0.5)
    reflection_container.tool_learning.record_tool_attempt("tenant_1", "mock_tool", success=True, latency=0.3)
    reflection_container.confidence_engine.calibrate_category("tenant_1", "cat_test", 0.9, 0.9)
    
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
        agentic_reflection=reflection_container,
    )
    
    return app


def test_reflection_api_endpoints(app_with_reflection):
    client = TestClient(app_with_reflection)
    
    # 1. POST /agentic/reflection/run
    steps = [
        {"node_id": "step_1", "tool": "seo_audit", "success": True, "duration": 1.0, "cost_dollars": 0.05}
    ]
    res = client.post("/agentic/reflection/run?execution_id=exec_100", json=steps)
    assert res.status_code == 200
    assert res.json()["total_steps"] == 1
    
    # 2. GET /agentic/reflection/{id}
    res = client.get("/agentic/reflection/exec_100")
    assert res.status_code == 200
    assert res.json()["total_steps"] == 1
    
    # 3. GET /agentic/learning/provider-scores
    res = client.get("/agentic/learning/provider-scores")
    assert res.status_code == 200
    assert len(res.json()) == 1
    assert res.json()[0]["provider_name"] == "mock_prov"
    
    # 4. GET /agentic/learning/tool-scores
    res = client.get("/agentic/learning/tool-scores")
    assert res.status_code == 200
    assert len(res.json()) == 1
    assert res.json()[0]["tool_name"] == "mock_tool"
    
    # 5. GET /agentic/learning/confidence
    res = client.get("/agentic/learning/confidence?category=cat_test")
    assert res.status_code == 200
    assert res.json()["calibration_factor"] == 1.0
