"""Keyword Opportunity Trigger (Phase 3)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enterprise_intelligence.observation.models import ObservationEvent, EventCategory
from enterprise_intelligence.knowledge.enterprise_graph import EnterpriseGraph
from enterprise_intelligence.goal_generation.models import AutonomousGoal
from enterprise_intelligence.goal_generation.triggers.base import BaseTrigger
from agentic.goal.models import GoalContext, GoalPriority, GoalConstraints, StructuredObjective, RiskLevel

__all__ = ["KeywordOpportunityTrigger"]


class KeywordOpportunityTrigger(BaseTrigger):
    trigger_name = "keyword_opportunity"

    def evaluate(self, event: ObservationEvent, graph: EnterpriseGraph) -> AutonomousGoal | None:
        if event.category != EventCategory.COMPETITOR or event.source_ref != "keyword_gap":
            return None

        keyword = event.data.get("keyword", "new_topic")
        raw_obj = f"Capitalise on new keyword opportunity: {keyword}"
        obj = StructuredObjective(
            target_metric="organic_impressions",
            magnitude=500,
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
            expiration_at=datetime.now(timezone.utc) + timedelta(days=5),
            estimated_roi=1.4,
            success_criteria=f"Content targeting keyword '{keyword}' created and ranks in top 50",
            confidence=0.75,
        )
