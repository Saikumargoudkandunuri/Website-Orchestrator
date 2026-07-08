"""Enterprise Intelligence persistence schema — SQLAlchemy ORM models (Final Milestone).

On its own ``EnterpriseIntelligenceBase``, separate from ``BrainBase``,
``GrowthBase``, ``IntelligenceBase``, etc., so no existing migration or
model-sync check is affected.

All tables are tenant-scoped (``tenant_id`` + ``site_id``).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Index, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

try:
    from sqlalchemy import JSON
except ImportError:  # pragma: no cover
    from sqlalchemy import Text as JSON  # type: ignore[assignment]

from sqlalchemy import Engine as SAEngine

__all__ = [
    "EnterpriseIntelligenceBase",
    "ObservationEventRow",
    "CorrelatedEventGroupRow",
    "EnterpriseNodeRow",
    "EnterpriseEdgeRow",
    "create_enterprise_intelligence_tables",
]


class EnterpriseIntelligenceBase(DeclarativeBase):
    """Declarative base for the Final Milestone Enterprise Intelligence tables."""


# ---------------------------------------------------------------------------
# Phase 1 — Observation tables
# ---------------------------------------------------------------------------

class ObservationEventRow(EnterpriseIntelligenceBase):
    """Append-only observation event storage."""

    __tablename__ = "ei_observation_events"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    site_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    category: Mapped[str] = mapped_column(String, nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String, nullable=False)
    source_engine: Mapped[str] = mapped_column(String, nullable=False)
    source_ref: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    data: Mapped[dict] = mapped_column(JSON, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    __table_args__ = (
        Index("ix_ei_obs_tenant_site_cat", "tenant_id", "site_id", "category"),
        Index("ix_ei_obs_tenant_created", "tenant_id", "created_at"),
    )


class CorrelatedEventGroupRow(EnterpriseIntelligenceBase):
    """Correlated event group storage."""

    __tablename__ = "ei_correlated_event_groups"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    event_ids: Mapped[dict] = mapped_column(JSON, nullable=False)  # list stored as JSON
    correlation_type: Mapped[str] = mapped_column(String, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_ei_corr_tenant", "tenant_id"),
    )


# ---------------------------------------------------------------------------
# Phase 2 — Enterprise Knowledge Graph tables
# ---------------------------------------------------------------------------

class EnterpriseNodeRow(EnterpriseIntelligenceBase):
    """Enterprise knowledge graph node."""

    __tablename__ = "ei_enterprise_nodes"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    site_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    node_type: Mapped[str] = mapped_column(String, nullable=False, index=True)
    label: Mapped[str] = mapped_column(String, nullable=False)
    properties: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    provenance: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_ei_nodes_tenant_site_type", "tenant_id", "site_id", "node_type"),
    )


class EnterpriseEdgeRow(EnterpriseIntelligenceBase):
    """Enterprise knowledge graph edge."""

    __tablename__ = "ei_enterprise_edges"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    site_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    edge_type: Mapped[str] = mapped_column(String, nullable=False, index=True)
    from_node_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    to_node_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    properties: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    provenance: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_ei_edges_tenant_site_type", "tenant_id", "site_id", "edge_type"),
        Index("ix_ei_edges_from_to", "from_node_id", "to_node_id"),
    )


def create_enterprise_intelligence_tables(engine: SAEngine) -> None:
    """Create all Enterprise Intelligence tables if they don't exist."""
    EnterpriseIntelligenceBase.metadata.create_all(engine)
