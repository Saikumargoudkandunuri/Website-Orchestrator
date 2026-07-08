"""GoalGenerator core (Phase 3).

Coordinates running observation events through registered triggers,
performing de-duplication against existing Goals, and enforcing safety
governance constraints.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select

from intelligence.repositories._session import SessionMixin
from agentic.goal.repositories import GoalRepository, GoalRecord
from agentic.goal.models import Goal, GoalStatus
from enterprise_intelligence.observation.models import ObservationEvent
from enterprise_intelligence.knowledge.enterprise_graph import EnterpriseGraph
from enterprise_intelligence.goal_generation.models import AutonomousGoal
from enterprise_intelligence.goal_generation.triggers.base import BaseTrigger

# Import all 10 triggers
from enterprise_intelligence.goal_generation.triggers.ranking_dropped import RankingDroppedTrigger
from enterprise_intelligence.goal_generation.triggers.competitor_improved import CompetitorImprovedTrigger
from enterprise_intelligence.goal_generation.triggers.backlinks_disappeared import BacklinksDisappearedTrigger
from enterprise_intelligence.goal_generation.triggers.pages_stale import PagesStaleTrigger
from enterprise_intelligence.goal_generation.triggers.keyword_opportunity import KeywordOpportunityTrigger
from enterprise_intelligence.goal_generation.triggers.cwv_degraded import CwvDegradedTrigger
from enterprise_intelligence.goal_generation.triggers.local_listings_inconsistent import LocalListingsInconsistentTrigger
from enterprise_intelligence.goal_generation.triggers.reviews_decreased import ReviewsDecreasedTrigger
from enterprise_intelligence.goal_generation.triggers.cost_increasing import CostIncreasingTrigger
from enterprise_intelligence.goal_generation.triggers.conversion_dropped import ConversionDroppedTrigger

__all__ = ["GoalGenerator"]

logger = logging.getLogger(__name__)


class GoalGenerator(SessionMixin):
    """Core goal generator that maps observations to structured goals.

    Enforces that machine-originated goals are safely gated, de-duplicated,
    and structured identically to human-originated goals.
    """

    def __init__(
        self,
        session_source: Any,
        tenant_id: str,
        goal_repo: GoalRepository,
    ) -> None:
        super().__init__(session_source, tenant_id=tenant_id)
        self._goal_repo = goal_repo
        self._triggers: list[BaseTrigger] = [
            RankingDroppedTrigger(),
            CompetitorImprovedTrigger(),
            BacklinksDisappearedTrigger(),
            PagesStaleTrigger(),
            KeywordOpportunityTrigger(),
            CwvDegradedTrigger(),
            LocalListingsInconsistentTrigger(),
            ReviewsDecreasedTrigger(),
            CostIncreasingTrigger(),
            ConversionDroppedTrigger(),
        ]

    def register_trigger(self, trigger: BaseTrigger) -> None:
        """Register a new custom trigger."""
        self._triggers.append(trigger)

    def process_event(
        self, event: ObservationEvent, graph: EnterpriseGraph
    ) -> list[AutonomousGoal]:
        """Process a single event, generating and returning any matching goals.

        Validates that generated goals do not conflict with existing active
        or recently created goals (de-duplication).
        """
        generated: list[AutonomousGoal] = []
        for trigger in self._triggers:
            goal = trigger.evaluate(event, graph)
            if goal:
                # Check for duplication before proceeding
                if self._is_duplicate(goal):
                    logger.info(
                        "De-duplicated goal from trigger %s for site %s",
                        trigger.trigger_name,
                        event.site_id,
                    )
                    continue
                
                # Check if goal has expired (should not persist expired goals)
                if goal.expiration_at and goal.expiration_at < datetime.now(timezone.utc):
                    continue

                # Ensure status is PENDING by default so it's ready for planning
                goal.status = GoalStatus.PENDING
                
                # Save via repository (Backward compatibility: SqlAlchemyGoalRepository takes Goal base class)
                self._goal_repo.save(goal)
                generated.append(goal)

        return generated

    def _is_duplicate(self, candidate: AutonomousGoal) -> bool:
        """Check if a similar goal exists in the last 24 hours."""
        tenant = self._resolve_tenant(candidate.context.tenant_id)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

        with self._session() as session:
            # Query GoalRecord from database
            stmt = select(GoalRecord).where(
                GoalRecord.tenant_id == tenant,
                GoalRecord.created_at >= cutoff,
            )
            records = session.execute(stmt).scalars().all()

            for r in records:
                existing_payload = r.payload
                # Check target site
                existing_site = existing_payload.get("structured_objective", {}).get("target_site_id")
                cand_site = candidate.structured_objective.target_site_id if candidate.structured_objective else None
                if existing_site != cand_site:
                    continue

                # Check trigger/objective target metric
                existing_metric = existing_payload.get("structured_objective", {}).get("target_metric")
                cand_metric = candidate.structured_objective.target_metric if candidate.structured_objective else None
                if existing_metric == cand_metric:
                    # Duplicate detected
                    return True

        return False
