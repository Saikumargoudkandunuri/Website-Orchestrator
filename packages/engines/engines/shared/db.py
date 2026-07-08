"""Engine persistence schema — SQLAlchemy ORM models (Milestone 3).

Deliberately on its **own** ``EnginesBase``, separate from both Digital_Twin's
``Base`` and Milestone 2's ``IntelligenceBase``, so neither the M1
migration-model-sync check nor M2's ``create_intelligence_tables`` are affected.

One uniform design across all ten engines plus the audit-job table:
- Each engine output table is append-only and versioned (same ``id + version``
  pattern as Milestone 2's ``knowledge_objects`` table).
- ``payload`` is a JSON column carrying the full typed Pydantic model — the
  engine's repository deserialises it at the boundary, so domain code never
  sees raw JSON.
- Every table is scoped by ``tenant_id`` AND a ``site_id`` or ``page_id``
  (depending on whether the engine is sitewide or per-page), satisfying the
  Milestone 3 multi-tenancy requirement (§7).
- ``AuditJobRow`` tracks the lifecycle of a full ten-engine sitewide audit
  triggered via ``POST /engines/audit``, supporting the async-friendly status/
  results pattern required by §6.

:func:`create_engine_tables` is the single provisioning call the composition
root makes — analogous to ``create_intelligence_tables`` in Milestone 2.
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
    "EnginesBase",
    # Ten engine output tables
    "TechnicalSeoAuditRow",
    "SiteArchitectureReportRow",
    "KeywordEngineReportRow",
    "ContentEngineReportRow",
    "CompetitorIntelligenceReportRow",
    "BacklinkIntelligenceReportRow",
    "TopicalAuthorityReportRow",
    "SeoScoreReportRow",
    "OpportunityReportRow",
    "RecommendationReportRow",
    # Audit job table
    "AuditJobRow",
    # Provisioning helper
    "create_engine_tables",
]


class EnginesBase(DeclarativeBase):
    """Declarative base for the Milestone 3 engine tables."""


# ---------------------------------------------------------------------------
# Per-page engine output tables
# ---------------------------------------------------------------------------

class TechnicalSeoAuditRow(EnginesBase):
    """Append-only per-page Technical SEO audit output (§4.1)."""

    __tablename__ = "engine_technical_seo_audits"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    site_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    page_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_tech_seo_tenant_page_version", "tenant_id", "page_id", "version"),
    )


class KeywordEngineReportRow(EnginesBase):
    """Append-only per-page Keyword Intelligence engine output (§4.3)."""

    __tablename__ = "engine_keyword_reports"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    site_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    page_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_kw_engine_tenant_page_version", "tenant_id", "page_id", "version"),
    )


class ContentEngineReportRow(EnginesBase):
    """Append-only per-page Content Intelligence engine output (§4.4)."""

    __tablename__ = "engine_content_reports"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    site_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    page_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_content_engine_tenant_page_version", "tenant_id", "page_id", "version"),
    )


class SeoScoreReportRow(EnginesBase):
    """Append-only per-page SEO Scoring engine output (§4.8)."""

    __tablename__ = "engine_seo_score_reports"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    site_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    page_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_seo_score_tenant_page_version", "tenant_id", "page_id", "version"),
    )


# ---------------------------------------------------------------------------
# Sitewide engine output tables
# ---------------------------------------------------------------------------

class SiteArchitectureReportRow(EnginesBase):
    """Append-only sitewide Site Architecture engine output (§4.2)."""

    __tablename__ = "engine_site_architecture_reports"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    site_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_site_arch_tenant_site_version", "tenant_id", "site_id", "version"),
    )


class CompetitorIntelligenceReportRow(EnginesBase):
    """Append-only sitewide Competitor Intelligence engine output (§4.5)."""

    __tablename__ = "engine_competitor_reports"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    site_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_competitor_tenant_site_version", "tenant_id", "site_id", "version"),
    )


class BacklinkIntelligenceReportRow(EnginesBase):
    """Append-only sitewide Backlink Intelligence engine output (§4.6)."""

    __tablename__ = "engine_backlink_reports"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    site_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_backlink_tenant_site_version", "tenant_id", "site_id", "version"),
    )


class TopicalAuthorityReportRow(EnginesBase):
    """Append-only sitewide Topical Authority engine output (§4.7)."""

    __tablename__ = "engine_topical_authority_reports"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    site_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_topical_auth_tenant_site_version", "tenant_id", "site_id", "version"),
    )


class OpportunityReportRow(EnginesBase):
    """Append-only sitewide Opportunity engine output (§4.9)."""

    __tablename__ = "engine_opportunity_reports"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    site_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_opportunity_tenant_site_version", "tenant_id", "site_id", "version"),
    )


class RecommendationReportRow(EnginesBase):
    """Append-only Recommendation engine output (§4.10, sitewide or per-page)."""

    __tablename__ = "engine_recommendation_reports"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    site_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    # page_id is nullable — a sitewide report has no single page_id.
    page_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_rec_tenant_site_version", "tenant_id", "site_id", "version"),
    )


# ---------------------------------------------------------------------------
# Audit job table — async full-site audit lifecycle (§6, §9)
# ---------------------------------------------------------------------------

class AuditJobRow(EnginesBase):
    """Tracks the lifecycle of a full ten-engine sitewide audit (§6).

    Status values: ``pending`` → ``running`` → ``completed`` | ``partial``
    | ``failed``.  ``engines_completed`` and ``engines_failed`` are JSON
    arrays so the orchestrator can update them incrementally without
    replacing the whole row.
    """

    __tablename__ = "engine_audit_jobs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    site_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    engines_requested: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    engines_completed: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    engines_failed: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    result_summary: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_audit_job_tenant_site", "tenant_id", "site_id"),
    )


# ---------------------------------------------------------------------------
# Provisioning helper
# ---------------------------------------------------------------------------

def create_engine_tables(engine: SAEngine) -> None:
    """Create all Milestone 3 engine tables on ``engine`` if they do not exist.

    Analogous to ``create_intelligence_tables`` in Milestone 2 — called once
    by the composition root so tables are available before the first request.
    Does not affect the Digital_Twin or Intelligence tables.
    """
    EnginesBase.metadata.create_all(engine)
