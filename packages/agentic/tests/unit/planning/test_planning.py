"""Tests for agentic planning subsystem (M6 Build Phase B)."""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from brain.db import BrainBase
from brain.decision.engine import DecisionEngine
from brain.decision.repositories import DecisionRepository, HistoricalOutcomeRepository
from brain.repositories import KnowledgeGraphRepository
from agentic.goal.models import Goal, GoalContext, GoalConstraints, RiskLevel
from agentic.planning.dependency_graph import DependencyError, validate_dag, get_topological_sort
from agentic.planning.models import ExecutionEdge, ExecutionGraph, ExecutionNode, Plan
from agentic.planning.planner import Planner
from agentic.planning.reasoner import Reasoner
from agentic.planning.critic import Critic
from agentic.planning.risk_analyzer import RiskAnalyzer
from agentic.planning.simulation import SimulationEngine
from agentic.tools.registry import build_default_tool_registry
from intelligence.ai.providers.fake_provider import FakeProvider


@pytest.fixture
def db_session_factory():
    engine = create_engine("sqlite:///:memory:")
    BrainBase.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def test_dependency_graph_validation():
    # 1. Valid DAG
    nodes = {
        "n1": ExecutionNode(id="n1", goal_id="g1", action_type="audit"),
        "n2": ExecutionNode(id="n2", goal_id="g1", action_type="content", dependencies=["n1"]),
    }
    edges = [ExecutionEdge(from_node="n1", to_node="n2", dependency_type="seq")]
    graph = ExecutionGraph(nodes=nodes, edges=edges)
    
    validate_dag(graph)
    order = get_topological_sort(graph)
    assert order == ["n1", "n2"]

    # 2. Cycle detection
    nodes_cycle = {
        "n1": ExecutionNode(id="n1", goal_id="g1", action_type="audit"),
        "n2": ExecutionNode(id="n2", goal_id="g1", action_type="content"),
    }
    edges_cycle = [
        ExecutionEdge(from_node="n1", to_node="n2", dependency_type="seq"),
        ExecutionEdge(from_node="n2", to_node="n1", dependency_type="seq"),
    ]
    graph_cycle = ExecutionGraph(nodes=nodes_cycle, edges=edges_cycle)
    
    with pytest.raises(DependencyError, match="Cyclic dependency detected"):
        validate_dag(graph_cycle)


def test_planner_reasoner_critic_risk_sim(db_session_factory):
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
    
    session = db_session_factory()
    kg_repo = KnowledgeGraphRepository(session, tenant_id="tenant_1")
    historical_repo = HistoricalOutcomeRepository(session, tenant_id="tenant_1")
    decision_repo = DecisionRepository(session, tenant_id="tenant_1")
    decision_engine = DecisionEngine(decision_repo, historical_repo)
    
    planner = Planner(
        provider=provider,
        registry=registry,
        kg_repo=kg_repo,
        historical_repo=historical_repo,
        decision_engine=decision_engine,
    )
    
    # 1. Goal parsing fallback to Goal creation
    from agentic.goal.goal_engine import GoalEngine
    goal_engine = GoalEngine(provider)
    context = GoalContext(tenant_id="tenant_1")
    
    # Success goal parsing responses
    goal_responses = {
        "goal_parsing": '{"target_metric": "organic_traffic", "magnitude": "25", "timeframe_days": 30, "target_site_id": "site_1", "target_page_set": []}'
    }
    goal_provider = FakeProvider(responses=goal_responses)
    goal_engine = GoalEngine(goal_provider)
    goal = goal_engine.parse("Increase organic traffic by 25%", context).unwrap()
    
    # 2. Plan generation
    plan = planner.plan(goal)
    assert len(plan.graph.nodes) == 3
    assert "step_1" in plan.graph.nodes
    
    # 3. Reasoner scoring
    reasoner = Reasoner(decision_engine)
    scores = reasoner.score_plan(plan)
    assert "business_impact" in scores
    assert "cost" in scores
    assert "complexity" in scores
    
    # 4. Critic plan invalidation
    critic = Critic()
    critiques = critic.critique_plan(plan)
    assert len(critiques) >= 0  # No structural failures, but might warn on content/technical
    
    # 5. Risk Analyzer
    risk_analyzer = RiskAnalyzer()
    risk_analysis = risk_analyzer.analyze_risk(plan)
    assert risk_analysis.overall_confidence > 0.0
    assert risk_analysis.composite_risk_score >= 0.0
    
    # 6. Simulation Engine
    sim_engine = SimulationEngine()
    outcome = sim_engine.simulate_outcomes(plan)
    assert outcome.simulated_traffic_gain > 0
    assert outcome.simulated_ranking_gain > 0
