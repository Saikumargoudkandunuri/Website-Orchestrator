"""Integration tests for planning API surface."""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from brain.db import BrainBase
from brain.decision.engine import DecisionEngine
from brain.decision.repositories import DecisionRepository, HistoricalOutcomeRepository
from brain.repositories import KnowledgeGraphRepository
from api.app import create_app
from agentic.goal.models import Goal, GoalContext, StructuredObjective
from agentic.goal.repositories import InMemoryGoalRepository
from agentic.planning.wiring import build_planning_container
from agentic.tools.registry import build_default_tool_registry
from intelligence.ai.providers.fake_provider import FakeProvider


@pytest.fixture
def app_with_agentic():
    # Setup dependencies
    responses = {
        "plan_decomposition": (
            '{"nodes": ['
            '  {"id": "step_1", "action_type": "technical_seo_audit", "estimated_duration": 1.0, "estimated_cost": 2.0, "estimated_tokens": 500, "business_value": 0.8, "rollback_strategy": "revert"},'
            '  {"id": "step_2", "action_type": "content_generation", "estimated_duration": 2.0, "estimated_cost": 3.0, "estimated_tokens": 1000, "dependencies": ["step_1"]},'
            '  {"id": "step_3", "action_type": "publish", "estimated_duration": 0.5, "estimated_cost": 0.5, "estimated_tokens": 100, "dependencies": ["step_2"]}'
            '], "edges": ['
            '  {"from_node": "step_1", "to_node": "step_2"},'
            '  {"from_node": "step_2", "to_node": "step_3"}'
            ']}'
        )
    }
    provider = FakeProvider(responses=responses)
    registry = build_default_tool_registry()
    
    # SQLite in-memory DB
    from sqlalchemy.pool import StaticPool
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # Import records to register them with metadata
    from agentic.planning.repositories import PlanRecord, ExecutionGraphRecord, SimulationRecord
    from agentic.goal.repositories import GoalRecord
    BrainBase.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    
    session = session_factory()
    kg_repo = KnowledgeGraphRepository(session, tenant_id="tenant_1")
    historical_repo = HistoricalOutcomeRepository(session, tenant_id="tenant_1")
    decision_repo = DecisionRepository(session, tenant_id="tenant_1")
    decision_engine = DecisionEngine(decision_repo, historical_repo)
    
    container = build_planning_container(
        session_factory,
        "tenant_1",
        provider=provider,
        registry=registry,
        kg_repo=kg_repo,
        historical_repo=historical_repo,
        decision_engine=decision_engine,
    )
    
    goal_repo = InMemoryGoalRepository()
    # Pre-populate a Goal
    goal = Goal(
        id="goal_1",
        raw_objective="Do something",
        structured_objective=StructuredObjective(
            target_metric="organic_traffic",
            magnitude="25",
            timeframe_days=30,
            target_site_id="site_1",
        ),
        context=GoalContext(tenant_id="tenant_1"),
    )
    goal_repo.save(goal)
    
    # Create the app manually injecting subsystems to avoid loading production settings
    from unittest.mock import MagicMock
    app = create_app(
        crawler=MagicMock(),
        digital_twin=MagicMock(),
        check_engine=MagicMock(),
        fix_generator=MagicMock(),
        governance=MagicMock(),
        tenant_id="tenant_1",
        agentic_planning=container,
        goal_repo=goal_repo,
    )
    
    return app


def test_planning_api_endpoints(app_with_agentic):
    client = TestClient(app_with_agentic)
    
    # 1. POST /agentic/goals/{id}/plan
    res = client.post("/agentic/goals/goal_1/plan")
    assert res.status_code == 200
    plan_data = res.json()
    assert plan_data["goal_id"] == "goal_1"
    plan_id = plan_data["id"]
    
    # 2. GET /agentic/plans/{id}
    res = client.get(f"/agentic/plans/{plan_id}")
    assert res.status_code == 200
    assert res.json()["id"] == plan_id
    
    # 3. GET /agentic/plans/{id}/graph
    res = client.get(f"/agentic/plans/{plan_id}/graph")
    assert res.status_code == 200
    assert "nodes" in res.json()
    
    # 4. POST /agentic/plans/{id}/simulate
    res = client.post(f"/agentic/plans/{plan_id}/simulate")
    assert res.status_code == 200
    assert "simulated_traffic_gain" in res.json()
    
    # 5. GET /agentic/plans/{id}/alternatives
    res = client.get(f"/agentic/plans/{plan_id}/alternatives")
    assert res.status_code == 200
    assert len(res.json()) > 0
