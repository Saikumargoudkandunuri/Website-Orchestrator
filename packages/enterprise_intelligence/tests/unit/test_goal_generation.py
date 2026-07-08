"""Phase 3 — Autonomous Goal Generation unit tests.

Tests cover: trigger evaluations, GoalGenerator routing, database de-duplication,
expiration filters, and safety/governance boundaries.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from brain.db import BrainBase
from agentic.goal.models import GoalStatus, GoalPriority, RiskLevel
from agentic.goal.repositories import SqlAlchemyGoalRepository, GoalRecord
from enterprise_intelligence.db import create_enterprise_intelligence_tables
from enterprise_intelligence.observation.models import ObservationEvent, EventCategory, EventSeverity
from enterprise_intelligence.knowledge.enterprise_graph import EnterpriseGraph
from enterprise_intelligence.goal_generation.models import AutonomousGoal
from enterprise_intelligence.goal_generation.generator import GoalGenerator
from enterprise_intelligence.goal_generation.triggers.base import BaseTrigger
from enterprise_intelligence.goal_generation.triggers.ranking_dropped import RankingDroppedTrigger
from enterprise_intelligence.goal_generation.triggers.cwv_degraded import CwvDegradedTrigger


# ---- Mock Triggers for testing ----

class MockTrigger(BaseTrigger):
    trigger_name = "mock_trigger"

    def evaluate(self, event: ObservationEvent, graph: EnterpriseGraph) -> AutonomousGoal | None:
        if event.category == EventCategory.CONTENT:
            # Return a valid goal
            from agentic.goal.models import GoalContext, StructuredObjective, GoalConstraints
            return AutonomousGoal(
                raw_objective="Mock content optimization",
                structured_objective=StructuredObjective(target_metric="content_freshness", magnitude=1),
                context=GoalContext(tenant_id=event.tenant_id),
                constraints=GoalConstraints(requires_human_approval_above_risk=RiskLevel.LOW),
                trigger_type=self.trigger_name,
                estimated_roi=1.0,
            )
        return None


# ---- Tests ----

class TestGoalTriggers:
    def test_ranking_dropped_trigger(self):
        trigger = RankingDroppedTrigger()
        graph = EnterpriseGraph(tenant_id="t1", site_id="s1")
        
        # Scenario 1: matching event
        event = ObservationEvent(
            tenant_id="t1",
            site_id="s1",
            category=EventCategory.RANKING,
            severity=EventSeverity.CRITICAL,
            source_engine="rank_tracking",
            source_ref="ref",
            title="Ranking drop",
            description="Page ranks dropped",
            data={"page_id": "p-123", "position_change": -11},
        )
        goal = trigger.evaluate(event, graph)
        assert goal is not None
        assert goal.priority == GoalPriority.HIGH
        assert goal.structured_objective.target_metric == "organic_traffic"
        assert "p-123" in goal.structured_objective.target_page_set
        assert goal.constraints.requires_human_approval_above_risk == RiskLevel.LOW

        # Scenario 2: non-matching event (low change)
        event_low = ObservationEvent(
            tenant_id="t1",
            site_id="s1",
            category=EventCategory.RANKING,
            severity=EventSeverity.INFO,
            source_engine="rank_tracking",
            source_ref="ref",
            title="Ranking stable",
            description="Page stable",
            data={"page_id": "p-123", "position_change": -1},
        )
        assert trigger.evaluate(event_low, graph) is None

    def test_cwv_degraded_trigger(self):
        trigger = CwvDegradedTrigger()
        graph = EnterpriseGraph(tenant_id="t1", site_id="s1")
        event = ObservationEvent(
            tenant_id="t1",
            site_id="s1",
            category=EventCategory.TECHNICAL,
            severity=EventSeverity.CRITICAL,
            source_engine="technical_seo",
            source_ref="cwv_regression",
            title="LCP regression",
            description="LCP metric degraded",
            data={"metric_name": "LCP"},
        )
        goal = trigger.evaluate(event, graph)
        assert goal is not None
        assert goal.priority == GoalPriority.URGENT
        assert goal.structured_objective.target_metric == "health_score"


class TestGoalGenerator:
    @pytest.fixture
    def db_session_factory(self):
        engine = create_engine("sqlite:///:memory:")
        BrainBase.metadata.create_all(engine)
        create_enterprise_intelligence_tables(engine)
        return sessionmaker(bind=engine)

    def test_generator_processes_event(self, db_session_factory):
        goal_repo = SqlAlchemyGoalRepository(db_session_factory, tenant_id="t1")
        generator = GoalGenerator(db_session_factory, tenant_id="t1", goal_repo=goal_repo)
        
        # Remove default triggers for predictable test, add MockTrigger
        generator._triggers = [MockTrigger()]
        
        event = ObservationEvent(
            tenant_id="t1",
            site_id="s1",
            category=EventCategory.CONTENT,
            source_engine="crawl",
            source_ref="stale",
            title="Stale page",
            description="Page is stale",
        )
        graph = EnterpriseGraph(tenant_id="t1", site_id="s1")
        
        goals = generator.process_event(event, graph)
        assert len(goals) == 1
        assert goals[0].raw_objective == "Mock content optimization"
        assert goals[0].status == GoalStatus.PENDING

        # Check repository persistence
        persisted = goal_repo.get("t1", goals[0].id)
        assert persisted is not None
        assert persisted.raw_objective == "Mock content optimization"

    def test_de_duplication(self, db_session_factory):
        goal_repo = SqlAlchemyGoalRepository(db_session_factory, tenant_id="t1")
        generator = GoalGenerator(db_session_factory, tenant_id="t1", goal_repo=goal_repo)
        generator._triggers = [MockTrigger()]
        
        event = ObservationEvent(
            tenant_id="t1",
            site_id="s1",
            category=EventCategory.CONTENT,
            source_engine="crawl",
            source_ref="stale",
            title="Stale page",
            description="Page is stale",
        )
        graph = EnterpriseGraph(tenant_id="t1", site_id="s1")
        
        # First process creates the goal
        goals1 = generator.process_event(event, graph)
        assert len(goals1) == 1

        # Second process with same event/metric within 24 hours should be de-duplicated
        goals2 = generator.process_event(event, graph)
        assert len(goals2) == 0

    def test_expiration_filter(self, db_session_factory):
        goal_repo = SqlAlchemyGoalRepository(db_session_factory, tenant_id="t1")
        generator = GoalGenerator(db_session_factory, tenant_id="t1", goal_repo=goal_repo)
        
        class ExpiredTrigger(BaseTrigger):
            trigger_name = "expired"
            def evaluate(self, event, graph):
                from agentic.goal.models import GoalContext, StructuredObjective
                return AutonomousGoal(
                    raw_objective="Expired goal",
                    structured_objective=StructuredObjective(target_metric="traffic", magnitude=1),
                    context=GoalContext(tenant_id=event.tenant_id),
                    trigger_type=self.trigger_name,
                    expiration_at=datetime.now(timezone.utc) - timedelta(seconds=1),  # already expired
                )
                
        generator._triggers = [ExpiredTrigger()]
        event = ObservationEvent(tenant_id="t1", site_id="s1", category=EventCategory.CONTENT, source_engine="crawl", source_ref="ref", title="title", description="desc")
        graph = EnterpriseGraph(tenant_id="t1", site_id="s1")
        
        goals = generator.process_event(event, graph)
        assert len(goals) == 0


class TestGoalSafetyBoundary:
    """Safety/Governance structural checks for Phase 3.

    Enforce that GoalGenerator contains ZERO imports or calls into tool
    execution paths (e.g. Executor, direct tool registrations, or execution api).
    """

    def test_no_execution_imports_in_generator(self):
        generator_file = os.path.join(
            os.path.dirname(__file__),
            os.pardir, os.pardir,
            "enterprise_intelligence", "goal_generation", "generator.py"
        )
        generator_file = os.path.normpath(generator_file)
        
        with open(generator_file, "r", encoding="utf-8") as f:
            source = f.read()

        forbidden_terms = ["Executor", "execute_node", "execute_mission"]
        violations = [term for term in forbidden_terms if term in source]
        assert not violations, f"GoalGenerator safety violation: references execution terms {violations}"
