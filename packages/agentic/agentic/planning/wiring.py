"""Dependency Injection wiring for the planning subsystem (M6 Build Phase B)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from brain.decision.engine import DecisionEngine
from brain.decision.repositories import HistoricalOutcomeRepository
from brain.repositories import KnowledgeGraphRepository
from agentic.goal.goal_engine import GoalEngine
from agentic.planning.critic import Critic
from agentic.planning.planner import Planner
from agentic.planning.reasoner import Reasoner
from agentic.planning.repositories import (
    ExecutionGraphRepository,
    PlanRepository,
    SimulationRepository,
)
from agentic.planning.risk_analyzer import RiskAnalyzer
from agentic.planning.simulation import SimulationEngine
from agentic.tools.registry import ToolRegistry
from intelligence.ai.provider_interface import AIProvider


@dataclass
class PlanningContainer:
    """Planning-layer repositories and services."""
    tenant_id: str
    plan_repo: PlanRepository
    graph_repo: ExecutionGraphRepository
    sim_repo: SimulationRepository
    planner: Planner
    reasoner: Reasoner
    critic: Critic
    risk_analyzer: RiskAnalyzer
    simulation_engine: SimulationEngine


def build_planning_container(
    session_source: Session | sessionmaker[Session] | object,
    tenant_id: str,
    *,
    provider: AIProvider,
    registry: ToolRegistry,
    kg_repo: KnowledgeGraphRepository,
    historical_repo: HistoricalOutcomeRepository,
    decision_engine: DecisionEngine,
) -> PlanningContainer:
    """Wire up the repositories and services for planning."""
    
    plan_repo = PlanRepository(session_source, tenant_id=tenant_id)
    graph_repo = ExecutionGraphRepository(session_source, tenant_id=tenant_id)
    sim_repo = SimulationRepository(session_source, tenant_id=tenant_id)
    
    planner = Planner(
        provider=provider,
        registry=registry,
        kg_repo=kg_repo,
        historical_repo=historical_repo,
        decision_engine=decision_engine,
    )
    
    reasoner = Reasoner(decision_engine=decision_engine)
    critic = Critic()
    risk_analyzer = RiskAnalyzer()
    simulation_engine = SimulationEngine()
    
    return PlanningContainer(
        tenant_id=tenant_id,
        plan_repo=plan_repo,
        graph_repo=graph_repo,
        sim_repo=sim_repo,
        planner=planner,
        reasoner=reasoner,
        critic=critic,
        risk_analyzer=risk_analyzer,
        simulation_engine=simulation_engine,
    )
