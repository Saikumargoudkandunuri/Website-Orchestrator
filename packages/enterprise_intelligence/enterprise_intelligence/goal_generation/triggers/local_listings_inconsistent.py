"""Local Listings Inconsistent Trigger (Phase 3)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enterprise_intelligence.observation.models import ObservationEvent, EventCategory
from enterprise_intelligence.knowledge.enterprise_graph import EnterpriseGraph
from enterprise_intelligence.goal_generation.models import AutonomousGoal
from enterprise_intelligence.goal_generation.triggers.base import BaseTrigger
from agentic.goal.models import GoalContext, GoalPriority, GoalConstraints, StructuredObjective, RiskLevel

__all__ = ["LocalListingsInconsistentTrigger"]


class LocalListingsInconsistentTrigger(BaseTrigger):
    trigger_name = "local_listings_inconsistent"

    def evaluate(self, event: ObservationEvent, graph: EnterpriseGraph) -> AutonomousGoal | None:
        if event.category != EventCategory.LOCAL_SEO:
            return None

        raw_obj = f"Reconcile NAP inconsistencies in local business citations"
        obj = StructuredObjective(
            target_metric="local_seo_score",
            magnitude=1.0,
            timeframe_days=14,
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
            expiration_at=datetime.now(timezone.utc) + timedelta(days=7),
            estimated_roi=1.1,
            success_criteria="Citations reconciled across top directories",
            confidence=0.85,
        )
