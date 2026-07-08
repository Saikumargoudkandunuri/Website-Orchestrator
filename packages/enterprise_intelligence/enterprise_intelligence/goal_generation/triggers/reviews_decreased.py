"""Reviews Decreased Trigger (Phase 3)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enterprise_intelligence.observation.models import ObservationEvent, EventCategory
from enterprise_intelligence.knowledge.enterprise_graph import EnterpriseGraph
from enterprise_intelligence.goal_generation.models import AutonomousGoal
from enterprise_intelligence.goal_generation.triggers.base import BaseTrigger
from agentic.goal.models import GoalContext, GoalPriority, GoalConstraints, StructuredObjective, RiskLevel

__all__ = ["ReviewsDecreasedTrigger"]


class ReviewsDecreasedTrigger(BaseTrigger):
    trigger_name = "reviews_decreased"

    def evaluate(self, event: ObservationEvent, graph: EnterpriseGraph) -> AutonomousGoal | None:
        if event.category != EventCategory.REPUTATION or event.source_ref != "review_volume":
            return None

        raw_obj = f"Initiate review acquisition sequence to recover rating volume"
        obj = StructuredObjective(
            target_metric="review_count",
            magnitude=10,
            timeframe_days=30,
            target_site_id=event.site_id,
        )
        
        ctx = GoalContext(tenant_id=event.tenant_id, project_id=event.site_id)
        
        return AutonomousGoal(
            raw_objective=raw_obj,
            structured_objective=obj,
            context=ctx,
            priority=GoalPriority.NORMAL,
            constraints=GoalConstraints(requires_human_approval_above_risk=RiskLevel.LOW),
            trigger_type=self.trigger_name,
            expiration_at=datetime.now(timezone.utc) + timedelta(days=10),
            estimated_roi=1.3,
            success_criteria="Obtain at least 10 positive user reviews",
            confidence=0.8,
        )
