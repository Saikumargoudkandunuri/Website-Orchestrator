"""Pages Stale Trigger (Phase 3)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enterprise_intelligence.observation.models import ObservationEvent, EventCategory
from enterprise_intelligence.knowledge.enterprise_graph import EnterpriseGraph
from enterprise_intelligence.goal_generation.models import AutonomousGoal
from enterprise_intelligence.goal_generation.triggers.base import BaseTrigger
from agentic.goal.models import GoalContext, GoalPriority, GoalConstraints, StructuredObjective, RiskLevel

__all__ = ["PagesStaleTrigger"]


class PagesStaleTrigger(BaseTrigger):
    trigger_name = "pages_stale"

    def evaluate(self, event: ObservationEvent, graph: EnterpriseGraph) -> AutonomousGoal | None:
        if event.category != EventCategory.CONTENT or event.source_ref != "stale_content":
            return None

        stale_pages = event.data.get("stale_pages", [])
        if not stale_pages:
            return None

        raw_obj = f"Update stale high-value content pages to maintain relevance"
        obj = StructuredObjective(
            target_metric="content_freshness",
            magnitude=len(stale_pages),
            timeframe_days=10,
            target_site_id=event.site_id,
            target_page_set=stale_pages,
        )
        
        ctx = GoalContext(tenant_id=event.tenant_id, project_id=event.site_id)
        
        return AutonomousGoal(
            raw_objective=raw_obj,
            structured_objective=obj,
            context=ctx,
            priority=GoalPriority.NORMAL,
            constraints=GoalConstraints(requires_human_approval_above_risk=RiskLevel.LOW),
            trigger_type=self.trigger_name,
            expiration_at=datetime.now(timezone.utc) + timedelta(days=14),
            estimated_roi=2.0,
            success_criteria="High-priority stale pages updated and re-indexed",
            confidence=1.0,
        )
