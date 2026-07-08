"""Core Web Vitals degraded Trigger (Phase 3)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enterprise_intelligence.observation.models import ObservationEvent, EventCategory, EventSeverity
from enterprise_intelligence.knowledge.enterprise_graph import EnterpriseGraph
from enterprise_intelligence.goal_generation.models import AutonomousGoal
from enterprise_intelligence.goal_generation.triggers.base import BaseTrigger
from agentic.goal.models import GoalContext, GoalPriority, GoalConstraints, StructuredObjective, RiskLevel

__all__ = ["CwvDegradedTrigger"]


class CwvDegradedTrigger(BaseTrigger):
    trigger_name = "cwv_degraded"

    def evaluate(self, event: ObservationEvent, graph: EnterpriseGraph) -> AutonomousGoal | None:
        if event.category != EventCategory.TECHNICAL or "cwv" not in event.source_ref.lower():
            return None

        metric_name = event.data.get("metric_name", "LCP")
        raw_obj = f"Audit and fix performance regression on metric: {metric_name}"
        obj = StructuredObjective(
            target_metric="health_score",
            magnitude=0.9,
            timeframe_days=7,
            target_site_id=event.site_id,
        )
        
        ctx = GoalContext(tenant_id=event.tenant_id, project_id=event.site_id)
        
        return AutonomousGoal(
            raw_objective=raw_obj,
            structured_objective=obj,
            context=ctx,
            priority=GoalPriority.URGENT,
            constraints=GoalConstraints(requires_human_approval_above_risk=RiskLevel.LOW),
            trigger_type=self.trigger_name,
            expiration_at=datetime.now(timezone.utc) + timedelta(days=3),
            estimated_roi=2.5,
            success_criteria=f"Metric {metric_name} returns to acceptable green thresholds",
            confidence=0.95,
        )
