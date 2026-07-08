"""Brain persistence schema — SQLAlchemy ORM models (Milestone 5).

On its own ``BrainBase``, separate from Digital_Twin's ``Base``,
Intelligence's ``IntelligenceBase``, Engine's ``EnginesBase``, and
Growth's ``GrowthBase``, so no existing migration/model-sync check is affected.

Tables:
- ``site_synthesis`` — versioned synthesis snapshots
- ``kg_nodes`` — knowledge graph node storage
- ``kg_edges`` — knowledge graph edge storage

All tables are tenant-scoped (``tenant_id`` + ``site_id``).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

try:
    from sqlalchemy import JSON
except ImportError:  # pragma: no cover
    from sqlalchemy import Text as JSON  # type: ignore[assignment]

from sqlalchemy import Engine as SAEngine

__all__ = [
    "BrainBase",
    "SiteSynthesisRow",
    "KGNodeRow",
    "KGEdgeRow",
    "create_brain_tables",
]

class BrainBase(DeclarativeBase):
    """Declarative base for the Milestone 5 Brain tables."""


class SiteSynthesisRow(BrainBase):
    """Append-only versioned site synthesis snapshot."""

    __tablename__ = "brain_site_synthesis"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    site_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_brain_synthesis_tenant_site_version", "tenant_id", "site_id", "version"),
    )


class KGNodeRow(BrainBase):
    """A single knowledge graph node."""

    __tablename__ = "brain_kg_nodes"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    site_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    node_type: Mapped[str] = mapped_column(String, nullable=False, index=True)
    label: Mapped[str] = mapped_column(String, nullable=False)
    properties: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    source_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_brain_kg_nodes_tenant_site_type", "tenant_id", "site_id", "node_type"),
    )


class KGEdgeRow(BrainBase):
    """A single knowledge graph edge."""

    __tablename__ = "brain_kg_edges"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    site_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    edge_type: Mapped[str] = mapped_column(String, nullable=False, index=True)
    from_node_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    to_node_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    properties: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_brain_kg_edges_tenant_site_type", "tenant_id", "site_id", "edge_type"),
        Index("ix_brain_kg_edges_from", "from_node_id"),
        Index("ix_brain_kg_edges_to", "to_node_id"),
    )


def create_brain_tables(engine: SAEngine) -> None:
    """Provision all Milestone 5 Brain tables (additive, idempotent)."""
    BrainBase.metadata.create_all(engine)

# Import decision models so they register with BrainBase.metadata
from brain.decision.db import DecisionRecord, HistoricalOutcomeRecord
from brain.scheduler.db import ScheduleRecord, AutomationRuleRecord, ExecutionLogRecord

