"""Tests for planning repositories."""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from brain.db import BrainBase
from agentic.planning.models import ExecutionGraph, Plan, ExecutionNode
from agentic.planning.simulation import SimulationOutcome, SimulatedTimeline
from agentic.planning.repositories import (
    PlanRepository,
    ExecutionGraphRepository,
    SimulationRepository,
)


@pytest.fixture
def db_session_factory():
    from sqlalchemy.pool import StaticPool
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # Register models by importing repositories
    from agentic.planning.repositories import PlanRecord, ExecutionGraphRecord, SimulationRecord
    from agentic.goal.repositories import GoalRecord
    BrainBase.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def test_repositories_save_and_retrieve(db_session_factory):
    session = db_session_factory()
    
    plan_repo = PlanRepository(session, tenant_id="tenant_1")
    graph_repo = ExecutionGraphRepository(session, tenant_id="tenant_1")
    sim_repo = SimulationRepository(session, tenant_id="tenant_1")
    
    # 1. Test PlanRepository
    plan = Plan(
        goal_id="goal_123",
        tenant_id="tenant_1",
        site_id="site_1",
        graph=ExecutionGraph(
            nodes={
                "n1": ExecutionNode(id="n1", goal_id="goal_123", action_type="audit")
            }
        )
    )
    
    plan_repo.save(plan)
    retrieved_plan = plan_repo.get("tenant_1", plan.id)
    assert retrieved_plan is not None
    assert retrieved_plan.goal_id == "goal_123"
    assert "n1" in retrieved_plan.graph.nodes
    
    # Check tenant isolation
    assert plan_repo.get("tenant_wrong", plan.id) is None
    
    # 2. Test ExecutionGraphRepository
    graph = ExecutionGraph(
        nodes={
            "n2": ExecutionNode(id="n2", goal_id="goal_123", action_type="content")
        }
    )
    graph_repo.save(plan.id, graph, tenant_id="tenant_1", site_id="site_1")
    retrieved_graph = graph_repo.get_for_plan("tenant_1", plan.id)
    assert retrieved_graph is not None
    assert "n2" in retrieved_graph.nodes
    
    # Check tenant isolation
    assert graph_repo.get_for_plan("tenant_wrong", plan.id) is None
    
    # 3. Test SimulationRepository
    outcome = SimulationOutcome(
        simulated_traffic_gain=150.0,
        simulated_ranking_gain=2.5,
        simulated_content_pages_created=3,
        total_estimated_cost_dollars=12.50,
        total_estimated_tokens=5000,
        timeline=SimulatedTimeline(
            total_duration_hours=4.5,
            critical_path_steps=3,
            concurrency_savings_hours=1.5,
        ),
        confidence_interval=(120.0, 180.0),
    )
    sim_repo.save(plan.id, outcome, tenant_id="tenant_1", site_id="site_1")
    retrieved_sim = sim_repo.get_for_plan("tenant_1", plan.id)
    assert retrieved_sim is not None
    assert retrieved_sim.simulated_traffic_gain == 150.0
    
    # Check tenant isolation
    assert sim_repo.get_for_plan("tenant_wrong", plan.id) is None
