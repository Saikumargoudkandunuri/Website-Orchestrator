"""Backlinks Disappeared Trigger (Phase 3)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enterprise_intelligence.observation.models import ObservationEvent, EventCategory
from enterprise_intelligence.knowledge.enterprise_graph import EnterpriseGraph
from enterprise_intelligence.goal_generation.models import AutonomousGoal
from enterprise_intelligence.goal_generation.triggers.base import BaseTrigger
from agentic.goal.models import GoalContext, GoalPriority, GoalConstraints, StructuredObjective, RiskLevel

__all__ = ["BacklinksDisappearedTrigger"]


class BacklinksDisappearedTrigger(BaseTrigger):
    trigger_name = "backlinks_disappeared"

    def evaluate(self, event: ObservationEvent, graph: EnterpriseGraph) -> AutonomousGoal | None:
        if event.category != EventCategory.BACKLINK:
            return None

        lost_count = event.data.get("lost_count", 0)
        if lost_count < 1:
            return None

        raw_obj = f"Reclaim lost backlinks to maintain domain authority"
        obj = StructuredObjective(
            target_metric="backlink_count",
            magnitude=lost_count,
            timeframe_days=30,
            target_site_id=event.site_id,
        )
        
        ctx = GoalContext(tenant_id=event.tenant_id, project_id=event.site_id)
        
        return AutonomousGoal(
            raw_objective=raw_obj,
            structured_objective=obj,
            context=ctx,
            priority=GoalPriority.HIGH,
            constraints=GoalConstraints(requires_human_approval_above_risk=RiskLevel.LOW),
            trigger_type=self.trigger_name,
            expiration_at=datetime.now(timezone.utc) + timedelta(days=10),
            estimated_roi=1.5,
            success_criteria="Reclaim at least 30% of lost links or build equivalent replacement authority",
            confidence=event.confidence,
        )
