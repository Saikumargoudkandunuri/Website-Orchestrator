"""Database schema for the Decision Engine on BrainBase."""

from __future__ import annotations

import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from brain.db import BrainBase

__all__ = [
    "DecisionRecord",
    "HistoricalOutcomeRecord",
]


class DecisionRecord(BrainBase):
    """Persistence for PrioritizedDecision."""
    __tablename__ = "decisions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False)
    site_id: Mapped[str] = mapped_column(String, nullable=False)
    
    source_engine: Mapped[str] = mapped_column(String, nullable=False)
    
    # JSON dump of the full PrioritizedDecision model
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
    )

    __table_args__ = (
        Index("ix_decisions_tenant_site", "tenant_id", "site_id"),
    )


class HistoricalOutcomeRecord(BrainBase):
    """Persistence for HistoricalOutcome."""
    __tablename__ = "historical_outcomes"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False)
    site_id: Mapped[str] = mapped_column(String, nullable=False)
    decision_id: Mapped[str] = mapped_column(String, nullable=False)
    
    is_success: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    performance_delta: Mapped[float | None] = mapped_column(Float, nullable=True)
    
    # JSON dump of the full HistoricalOutcome model
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
    )

    __table_args__ = (
        Index("ix_outcomes_tenant_site", "tenant_id", "site_id"),
        Index("ix_outcomes_decision", "decision_id"),
    )
