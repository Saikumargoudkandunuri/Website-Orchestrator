"""Conversion Dropped Trigger (Phase 3)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enterprise_intelligence.observation.models import ObservationEvent, EventCategory, EventSeverity
from enterprise_intelligence.knowledge.enterprise_graph import EnterpriseGraph
from enterprise_intelligence.goal_generation.models import AutonomousGoal
from enterprise_intelligence.goal_generation.triggers.base import BaseTrigger
from agentic.goal.models import GoalContext, GoalPriority, GoalConstraints, StructuredObjective, RiskLevel

__all__ = ["ConversionDroppedTrigger"]


class ConversionDroppedTrigger(BaseTrigger):
    trigger_name = "conversion_dropped"

    def evaluate(self, event: ObservationEvent, graph: EnterpriseGraph) -> AutonomousGoal | None:
        if event.category != EventCategory.ANALYTICS or event.source_ref != "conversion_rate":
            return None

        raw_obj = f"Perform UX audit and conversion rate optimization (CRO)"
        obj = StructuredObjective(
            target_metric="conversions",
            magnitude=1.2,
            timeframe_days=30,
            target_site_id=event.site_id,
        )
        
        ctx = GoalContext(tenant_id=event.tenant_id, project_id=event.site_id)
        
        return AutonomousGoal(
            raw_objective=raw_obj,
            structured_objective=obj,
            context=ctx,
            priority=GoalPriority.HIGH if event.severity == EventSeverity.CRITICAL else GoalPriority.NORMAL,
            constraints=GoalConstraints(requires_human_approval_above_risk=RiskLevel.LOW),
            trigger_type=self.trigger_name,
            expiration_at=datetime.now(timezone.utc) + timedelta(days=7),
            estimated_roi=2.0,
            success_criteria="Conversion rate returns to green threshold",
            confidence=0.85,
        )
