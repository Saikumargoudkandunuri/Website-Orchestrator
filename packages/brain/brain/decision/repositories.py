"""Repositories for the Decision Engine."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select

from intelligence.repositories._session import SessionMixin
from brain.decision.db import DecisionRecord, HistoricalOutcomeRecord
from brain.decision.models import HistoricalOutcome, PrioritizedDecision

__all__ = [
    "DecisionRepository",
    "HistoricalOutcomeRepository",
]


class DecisionRepository(SessionMixin):
    """Persistence for PrioritizedDecision models."""

    def save(self, decision: PrioritizedDecision) -> None:
        """Save a new decision or update an existing one."""
        with self.session() as session:
            record = session.get(DecisionRecord, decision.id)
            if not record:
                record = DecisionRecord(
                    id=decision.id,
                    tenant_id=decision.tenant_id,
                    site_id=decision.site_id,
                    source_engine=decision.source_engine,
                    payload=decision.model_dump(mode="json"),
                )
                session.add(record)
            else:
                record.payload = decision.model_dump(mode="json")
                record.source_engine = decision.source_engine
            session.commit()

    def get_all_for_site(
        self, tenant_id: str, site_id: str
    ) -> list[PrioritizedDecision]:
        """Load all decisions for a site."""
        with self.session() as session:
            stmt = select(DecisionRecord).where(
                DecisionRecord.tenant_id == tenant_id,
                DecisionRecord.site_id == site_id,
            )
            records = session.execute(stmt).scalars().all()
            return [
                PrioritizedDecision.model_validate(r.payload)
                for r in records
            ]


class HistoricalOutcomeRepository(SessionMixin):
    """Persistence for HistoricalOutcome models."""

    def save(self, outcome: HistoricalOutcome) -> None:
        """Save a new outcome or update an existing one."""
        with self.session() as session:
            record = session.get(HistoricalOutcomeRecord, outcome.id)
            if not record:
                record = HistoricalOutcomeRecord(
                    id=outcome.id,
                    tenant_id=outcome.tenant_id,
                    site_id=outcome.site_id,
                    decision_id=outcome.decision_id,
                    is_success=outcome.is_success,
                    performance_delta=outcome.performance_delta,
                    payload=outcome.model_dump(mode="json"),
                )
                session.add(record)
            else:
                record.is_success = outcome.is_success
                record.performance_delta = outcome.performance_delta
                record.payload = outcome.model_dump(mode="json")
            session.commit()

    def get_by_decision(self, tenant_id: str, decision_id: str) -> HistoricalOutcome | None:
        """Load the outcome associated with a decision."""
        with self.session() as session:
            stmt = select(HistoricalOutcomeRecord).where(
                HistoricalOutcomeRecord.tenant_id == tenant_id,
                HistoricalOutcomeRecord.decision_id == decision_id,
            )
            record = session.execute(stmt).scalar_one_or_none()
            if not record:
                return None
            return HistoricalOutcome.model_validate(record.payload)
