"""Competitor Improved Trigger (Phase 3)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enterprise_intelligence.observation.models import ObservationEvent, EventCategory
from enterprise_intelligence.knowledge.enterprise_graph import EnterpriseGraph
from enterprise_intelligence.goal_generation.models import AutonomousGoal
from enterprise_intelligence.goal_generation.triggers.base import BaseTrigger
from agentic.goal.models import GoalContext, GoalPriority, GoalConstraints, StructuredObjective, RiskLevel

__all__ = ["CompetitorImprovedTrigger"]


class CompetitorImprovedTrigger(BaseTrigger):
    trigger_name = "competitor_improved"

    def evaluate(self, event: ObservationEvent, graph: EnterpriseGraph) -> AutonomousGoal | None:
        if event.category != EventCategory.COMPETITOR:
            return None

        competitor = event.data.get("competitor_name", "competitor")
        raw_obj = f"Audit competitor {competitor} who gained visibility and optimize competing pages"
        
        obj = StructuredObjective(
            target_metric="keyword_gap",
            magnitude="gap_closure",
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
            expiration_at=datetime.now(timezone.utc) + timedelta(days=5),
            estimated_roi=1.2,
            success_criteria="Keyword overlap optimization implemented",
            confidence=0.8,
        )
