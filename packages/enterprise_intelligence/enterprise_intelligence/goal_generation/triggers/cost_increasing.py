"""Cost Increasing Trigger (Phase 3)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enterprise_intelligence.observation.models import ObservationEvent, EventCategory
from enterprise_intelligence.knowledge.enterprise_graph import EnterpriseGraph
from enterprise_intelligence.goal_generation.models import AutonomousGoal
from enterprise_intelligence.goal_generation.triggers.base import BaseTrigger
from agentic.goal.models import GoalContext, GoalPriority, GoalConstraints, StructuredObjective, RiskLevel

__all__ = ["CostIncreasingTrigger"]


class CostIncreasingTrigger(BaseTrigger):
    trigger_name = "cost_increasing"

    def evaluate(self, event: ObservationEvent, graph: EnterpriseGraph) -> AutonomousGoal | None:
        if event.category != EventCategory.COST:
            return None

        raw_obj = f"Optimize platform token usage and cache hit rate to lower costs"
        obj = StructuredObjective(
            target_metric="token_cost",
            magnitude="-15%",
            timeframe_days=14,
            target_site_id=event.site_id,
        )
        
        ctx = GoalContext(tenant_id=event.tenant_id, project_id=event.site_id)
        
        return AutonomousGoal(
            raw_objective=raw_obj,
            structured_objective=obj,
            context=ctx,
            priority=GoalPriority.LOW,
            constraints=GoalConstraints(requires_human_approval_above_risk=RiskLevel.LOW),
            trigger_type=self.trigger_name,
            expiration_at=datetime.now(timezone.utc) + timedelta(days=7),
            estimated_roi=3.0,  # strong return on spend reduction
            success_criteria="Token costs decrease by 15% on target engines",
            confidence=0.9,
        )
