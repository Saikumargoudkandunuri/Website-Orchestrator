"""Phase 4 — Autonomous Workflow Intelligence unit tests.

Tests cover: GoalMerger, RollbackPlanner, DynamicReplanning, and
LongRunningPlan serialization checks.
"""

from __future__ import annotations

from datetime import datetime, timezone
import pytest

from agentic.goal.models import Goal, StructuredObjective, GoalContext, GoalPriority, RiskLevel
from agentic.planning.models import Plan, ExecutionGraph, ExecutionNode
from enterprise_intelligence.observation.models import ObservationEvent, EventCategory, EventSeverity
from enterprise_intelligence.workflow.models import LongRunningPlan
from enterprise_intelligence.workflow.engine import GoalMerger, RollbackPlanner, WorkflowOrchestrator


class MockM1GovernanceService:
    def rollback_fix(self, tenant_id, fix_id, actor, rationale):
        return {"status": "rolled_back", "fix_id": fix_id}


class MockM6Planner:
    def plan(self, goal):
        return Plan(
            goal_id=goal.id,
            tenant_id=goal.context.tenant_id,
            site_id=goal.structured_objective.target_site_id or "default",
            graph=ExecutionGraph(
                nodes={
                    "replan_node": ExecutionNode(id="replan_node", goal_id=goal.id, action_type="technical_seo_audit")
                }
            )
        )


class TestGoalMerger:
    def test_merge_compatible_goals(self):
        merger = GoalMerger()
        
        ctx = GoalContext(tenant_id="t1")
        g1 = Goal(
            raw_objective="Optimize home page",
            structured_objective=StructuredObjective(target_metric="traffic", magnitude=1, target_site_id="s1", target_page_set=["home"]),
            context=ctx,
            priority=GoalPriority.NORMAL,
        )
        g2 = Goal(
            raw_objective="Optimize landing page",
            structured_objective=StructuredObjective(target_metric="traffic", magnitude=1, target_site_id="s1", target_page_set=["landing"]),
            context=ctx,
            priority=GoalPriority.HIGH,
        )
        
        merged = merger.merge_goals(g1, g2)
        assert merged is not None
        assert "Merged:" in merged.raw_objective
        assert merged.priority == GoalPriority.HIGH
        assert set(merged.structured_objective.target_page_set) == {"home", "landing"}

    def test_no_merge_different_metrics(self):
        merger = GoalMerger()
        ctx = GoalContext(tenant_id="t1")
        g1 = Goal(
            raw_objective="Optimize traffic",
            structured_objective=StructuredObjective(target_metric="traffic", magnitude=1, target_site_id="s1"),
            context=ctx,
        )
        g2 = Goal(
            raw_objective="Optimize conversions",
            structured_objective=StructuredObjective(target_metric="conversions", magnitude=1, target_site_id="s1"),
            context=ctx,
        )
        assert merger.merge_goals(g1, g2) is None


class TestRollbackPlanner:
    def test_plan_rollback_generates_nodes(self):
        gov = MockM1GovernanceService()
        planner = RollbackPlanner(gov)
        
        # Build plan with a publish step
        nodes = {
            "node-1": ExecutionNode(
                id="node-1",
                goal_id="g1",
                action_type="wp_publish",
                required_inputs={"suggested_fix_id": "fix-123"},
            )
        }
        plan = Plan(goal_id="g1", tenant_id="t1", site_id="s1", graph=ExecutionGraph(nodes=nodes))
        
        rollback_steps = planner.plan_rollback(plan, completed_nodes=["node-1"])
        assert len(rollback_steps) == 1
        assert rollback_steps[0].action_type == "governance_rollback"
        assert rollback_steps[0].required_inputs["suggested_fix_id"] == "fix-123"
        assert rollback_steps[0].approval_required is True


class TestDynamicReplanning:
    def test_mid_execution_replanning_triggers(self):
        planner = MockM6Planner()
        orchestrator = WorkflowOrchestrator(planner)
        
        # Build running plan
        nodes = {
            "step_1": ExecutionNode(
                id="step_1",
                goal_id="g1",
                action_type="content_generation",
                required_inputs={"page_ids": ["home"]},
            )
        }
        plan = Plan(goal_id="g1", tenant_id="t1", site_id="s1", graph=ExecutionGraph(nodes=nodes))
        
        # Event: critical CWV regression on the home page
        event = ObservationEvent(
            tenant_id="t1",
            site_id="s1",
            category=EventCategory.TECHNICAL,
            severity=EventSeverity.CRITICAL,
            source_engine="observability",
            source_ref="cwv_regression",
            title="LCP regression",
            description="LCP metric degraded",
            data={"page_id": "home"},
        )
        
        new_plan = orchestrator.evaluate_mid_execution_replanning(plan, event, active_step_id="step_1")
        assert new_plan is not None
        assert new_plan.version == plan.version + 1
        assert "replan_node" in new_plan.graph.nodes


class TestLongRunningPlan:
    def test_plan_fields(self):
        plan = LongRunningPlan(
            goal_id="g1",
            tenant_id="t1",
            site_id="s1",
            graph=ExecutionGraph(),
            is_recurring=True,
            cron_expression="0 0 * * *",
            checkpoint_state={"completed_steps": ["step1"]},
        )
        assert plan.is_recurring is True
        assert plan.cron_expression == "0 0 * * *"
        assert plan.checkpoint_state == {"completed_steps": ["step1"]}
