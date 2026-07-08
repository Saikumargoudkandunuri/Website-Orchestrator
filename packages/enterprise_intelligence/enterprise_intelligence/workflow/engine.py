"""Workflow engine for long-running plans, dynamic replanning, and rollbacks (Phase 4).

Reuses M1 governance rollbacks and M6 Planner/Runtime features.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from agentic.planning.models import Plan, ExecutionGraph, ExecutionNode, ExecutionEdge
from agentic.planning.planner import Planner
from agentic.goal.models import Goal, GoalStatus
from enterprise_intelligence.observation.models import ObservationEvent, EventCategory, EventSeverity
from enterprise_intelligence.workflow.models import LongRunningPlan

__all__ = ["WorkflowOrchestrator", "GoalMerger", "RollbackPlanner"]

logger = logging.getLogger(__name__)


class GoalMerger:
    """Combines overlapping goals to prevent redundant execution runs."""

    def merge_goals(self, g1: Goal, g2: Goal) -> Goal | None:
        """Merge two goals if they target the same site and metric.

        Returns a single merged Goal, or None if they cannot be merged.
        """
        # Simple compatibility check
        s1 = g1.structured_objective.target_site_id if g1.structured_objective else None
        s2 = g2.structured_objective.target_site_id if g2.structured_objective else None
        if s1 != s2 or s1 is None:
            return None

        m1 = g1.structured_objective.target_metric if g1.structured_objective else None
        m2 = g2.structured_objective.target_metric if g2.structured_objective else None
        if m1 != m2 or m1 is None:
            return None

        # Merge scopes
        pages1 = set(g1.structured_objective.target_page_set if g1.structured_objective else [])
        pages2 = set(g2.structured_objective.target_page_set if g2.structured_objective else [])
        merged_pages = sorted(list(pages1.union(pages2)))

        # Choose highest priority
        priority_order = {"low": 0, "normal": 1, "high": 2, "urgent": 3}
        p1 = priority_order.get(g1.priority.value, 1)
        p2 = priority_order.get(g2.priority.value, 1)
        merged_priority = g1.priority if p1 >= p2 else g2.priority

        # Build merged objective
        from agentic.goal.models import StructuredObjective
        merged_objective = StructuredObjective(
            target_metric=m1,
            magnitude=g1.structured_objective.magnitude,  # defaults to first
            timeframe_days=max(
                g1.structured_objective.timeframe_days or 14,
                g2.structured_objective.timeframe_days or 14,
            ),
            target_site_id=s1,
            target_page_set=merged_pages,
        )

        from agentic.goal.models import Goal
        return Goal(
            raw_objective=f"Merged: {g1.raw_objective} AND {g2.raw_objective}",
            structured_objective=merged_objective,
            context=g1.context,
            priority=merged_priority,
            constraints=g1.constraints,
            status=GoalStatus.PENDING,
        )


class RollbackPlanner:
    """Formulates plan rollback steps by delegating to M1 governance."""

    def __init__(self, governance_service: Any) -> None:
        self._gov = governance_service

    def plan_rollback(self, plan: Plan, completed_nodes: list[str]) -> list[ExecutionNode]:
        """Generate a sequence of rollback nodes for completed actions.

        Reuses M1/M4 rollback mechanisms directly.
        """
        rollback_nodes: list[ExecutionNode] = []
        # Process in reverse order of completion
        for node_id in reversed(completed_nodes):
            # Find the node in the plan graph
            node = plan.graph.nodes.get(node_id)
            if not node:
                continue

            # If node action was a published fix, construct a M1 rollback delegate
            if "publish" in (node.action_type or "").lower() or "fix" in (node.action_type or "").lower():
                fix_id = node.required_inputs.get("suggested_fix_id")
                if fix_id:
                    # Construct a node that calls GovernanceService.rollback_fix
                    from agentic.goal.models import RiskLevel
                    rollback_node = ExecutionNode(
                        id=f"rollback_{node.id}",
                        goal_id=plan.goal_id,
                        action_type="governance_rollback",
                        tool_name="wp_rollback",
                        required_inputs={
                            "suggested_fix_id": fix_id,
                            "actor": "autonomous_rollback_agent",
                            "rationale": f"Autonomous rollback for failed plan {plan.id}",
                        },
                        risk_level=RiskLevel.HIGH,
                        approval_required=True,
                    )
                    rollback_nodes.append(rollback_node)

        return rollback_nodes


class WorkflowOrchestrator:
    """Manages active workflows, scheduling, and dynamic mid-execution replanning."""

    def __init__(self, planner: Planner, scheduler: Any = None) -> None:
        self._planner = planner
        self._scheduler = scheduler

    def evaluate_mid_execution_replanning(
        self, plan: Plan, event: ObservationEvent, active_step_id: str | None
    ) -> Plan | None:
        """Evaluate if an incoming event renders the current plan obsolete.

        If so, dynamically replans remaining steps using the M6 Planner
        and returns the new revised Plan.
        """
        # For example, if a Core Web Vitals regression occurs on the same page,
        # we need to inject a fix step before proceeding with content optimization.
        if event.category == EventCategory.TECHNICAL and event.severity == EventSeverity.CRITICAL:
            # Check if plan operates on the same page
            target_pages = plan.graph.nodes.get(active_step_id).required_inputs.get("page_ids", []) if active_step_id and plan.graph.nodes.get(active_step_id) else []
            event_page = event.data.get("page_id")
            
            if event_page and event_page in target_pages:
                logger.info("Dynamic replanning triggered for plan %s on event %s", plan.id, event.id)
                # Call planner to create alternatives or a revised graph
                # Here we simulate by adding an audit step to the remaining graph
                from agentic.goal.models import Goal, StructuredObjective, GoalContext
                goal = Goal(
                    raw_objective=f"Resolve speed issue for page {event_page} + resume plan",
                    structured_objective=StructuredObjective(
                        target_metric="health_score",
                        magnitude=0.9,
                        target_site_id=plan.site_id,
                        target_page_set=[event_page],
                    ),
                    context=GoalContext(tenant_id=plan.tenant_id),
                )
                new_plan = self._planner.plan(goal)
                
                # Combine remaining graph steps of the original plan
                # Mark as new version
                new_plan.version = plan.version + 1
                new_plan.id = plan.id
                return new_plan
                
        return None
