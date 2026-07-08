"""Ranking Dropped Trigger (Phase 3)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enterprise_intelligence.observation.models import ObservationEvent, EventCategory, EventSeverity
from enterprise_intelligence.knowledge.enterprise_graph import EnterpriseGraph
from enterprise_intelligence.goal_generation.models import AutonomousGoal
from enterprise_intelligence.goal_generation.triggers.base import BaseTrigger
from agentic.goal.models import GoalContext, GoalPriority, GoalConstraints, StructuredObjective, RiskLevel

__all__ = ["RankingDroppedTrigger"]


class RankingDroppedTrigger(BaseTrigger):
    trigger_name = "ranking_dropped"

    def evaluate(self, event: ObservationEvent, graph: EnterpriseGraph) -> AutonomousGoal | None:
        if event.category != EventCategory.RANKING or event.severity not in (EventSeverity.WARNING, EventSeverity.CRITICAL):
            return None

        # Build goal
        page_id = event.data.get("page_id", "all")
        raw_obj = f"Recover ranking drop for page {page_id} by improving keyword visibility"
        
        obj = StructuredObjective(
            target_metric="organic_traffic",
            magnitude=2.0,  # e.g. double traffic back
            timeframe_days=30,
            target_site_id=event.site_id,
            target_page_set=[page_id] if page_id != "all" else [],
        )
        
        ctx = GoalContext(
            tenant_id=event.tenant_id,
            project_id=event.site_id,
        )

        # Autonomous goals default to low allowed risk level for auto-approval (very conservative)
        constraints = GoalConstraints(
            requires_human_approval_above_risk=RiskLevel.LOW,
            max_autonomous_steps=5,
        )

        return AutonomousGoal(
            raw_objective=raw_obj,
            structured_objective=obj,
            context=ctx,
            priority=GoalPriority.HIGH if event.severity == EventSeverity.CRITICAL else GoalPriority.NORMAL,
            constraints=constraints,
            trigger_type=self.trigger_name,
            expiration_at=datetime.now(timezone.utc) + timedelta(days=7),
            estimated_roi=1.8,
            success_criteria="Rank recovers back to baseline range",
            confidence=event.confidence,
        )
