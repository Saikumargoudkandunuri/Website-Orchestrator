"""Growth persistence schema — SQLAlchemy ORM models (Milestone 4).

Deliberately on its own ``GrowthBase``, separate from EnginesBase, IntelligenceBase,
and Digital_Twin's Base. This keeps all prior milestones' migration-model-sync
checks unaffected.

Design:
- Each growth engine output table is append-only and versioned (same pattern as
  Milestone 3 engines), except RankTracking and Analytics which are append-only
  time series using ``captured_at`` rather than ``version``.
- ``payload`` is a JSON column carrying the full typed Pydantic model.
- Every table carries ``tenant_id``, ``organization_id``, ``client_id``, and
  ``site_id`` (or ``page_id``/``site_id`` derived scoping) for row-level tenant
  isolation (§3.5, §8).

:func:`create_growth_tables` is the single provisioning call the composition
root makes.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

try:
    from sqlalchemy import JSON
except ImportError:  # pragma: no cover
    from sqlalchemy import Text as JSON  # type: ignore[assignment]

from sqlalchemy import Engine as SAEngine

__all__ = [
    "GrowthBase",
    # Engine output tables
    "ContentGenerationAssetRow",
    "ContentOptimizationReportRow",
    "LocalSeoReportRow",
    "ReputationReportRow",
    "RankTrackingSnapshotRow",
    "ReportArtifactRow",
    "AnalyticsSnapshotRow",
    "OutreachReportRow",
    # Agency management tables
    "OrganizationRow",
    "ClientRow",
    "TeamRow",
    "WorkspaceRow",
    "TaskRow",
    "NotificationRow",
    # Automation tables
    "AutomationRuleRow",
    "AutomationExecutionLogRow",
    # Rank tracking tracked keywords
    "TrackedKeywordRow",
    # Provisioning helper
    "create_growth_tables",
]


class GrowthBase(DeclarativeBase):
    """Declarative base for Milestone 4 growth tables."""


# ---------------------------------------------------------------------------
# Content Generation (ContentAsset — the governance entity)
# ---------------------------------------------------------------------------

class ContentGenerationAssetRow(GrowthBase):
    """ContentAsset governance entity (§2.2, §4.1)."""

    __tablename__ = "growth_content_assets"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    organization_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    client_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    site_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    page_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    asset_type: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="draft")
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_content_asset_tenant_site", "tenant_id", "site_id"),
        Index("ix_content_asset_status", "tenant_id", "site_id", "status"),
    )


# ---------------------------------------------------------------------------
# Content Optimization (per-page, versioned report)
# ---------------------------------------------------------------------------

class ContentOptimizationReportRow(GrowthBase):
    """Append-only per-page Content Optimization report (§4.2)."""

    __tablename__ = "growth_content_optimization_reports"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    organization_id: Mapped[str | None] = mapped_column(String, nullable=True)
    client_id: Mapped[str | None] = mapped_column(String, nullable=True)
    site_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    page_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_co_tenant_page_version", "tenant_id", "page_id", "version"),
    )


# ---------------------------------------------------------------------------
# Local SEO (sitewide/per-location, versioned report)
# ---------------------------------------------------------------------------

class LocalSeoReportRow(GrowthBase):
    """Append-only sitewide Local SEO report (§4.3)."""

    __tablename__ = "growth_local_seo_reports"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    organization_id: Mapped[str | None] = mapped_column(String, nullable=True)
    client_id: Mapped[str | None] = mapped_column(String, nullable=True)
    site_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_local_seo_tenant_site_version", "tenant_id", "site_id", "version"),
    )


# ---------------------------------------------------------------------------
# Reputation Management (sitewide/per-location, versioned report)
# ---------------------------------------------------------------------------

class ReputationReportRow(GrowthBase):
    """Append-only sitewide Reputation report (§4.4)."""

    __tablename__ = "growth_reputation_reports"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    organization_id: Mapped[str | None] = mapped_column(String, nullable=True)
    client_id: Mapped[str | None] = mapped_column(String, nullable=True)
    site_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_rep_mgmt_tenant_site_version", "tenant_id", "site_id", "version"),
    )


# ---------------------------------------------------------------------------
# Rank Tracking (append-only time series — NOT versioned report)
# ---------------------------------------------------------------------------

class RankTrackingSnapshotRow(GrowthBase):
    """Append-only rank tracking snapshot (time series, §4.5).

    Unlike other engine output tables this is a pure time series — no version
    number, just captured_at. Idempotency is enforced via the unique constraint
    on (tenant_id, site_id, keyword, device, geo, captured_at_date).
    """

    __tablename__ = "growth_ranking_snapshots"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    organization_id: Mapped[str | None] = mapped_column(String, nullable=True)
    client_id: Mapped[str | None] = mapped_column(String, nullable=True)
    site_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    page_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    keyword: Mapped[str] = mapped_column(String, nullable=False, index=True)
    device: Mapped[str] = mapped_column(String, nullable=False, default="desktop")
    geo: Mapped[str | None] = mapped_column(String, nullable=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)  # full RankingSnapshot

    __table_args__ = (
        Index("ix_rank_snapshot_tenant_site_keyword", "tenant_id", "site_id", "keyword"),
        Index("ix_rank_snapshot_time", "tenant_id", "site_id", "captured_at"),
    )


class TrackedKeywordRow(GrowthBase):
    """A keyword being tracked for a site (configuration, not time series)."""

    __tablename__ = "growth_tracked_keywords"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    organization_id: Mapped[str | None] = mapped_column(String, nullable=True)
    client_id: Mapped[str | None] = mapped_column(String, nullable=True)
    site_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    keyword: Mapped[str] = mapped_column(String, nullable=False)
    device: Mapped[str] = mapped_column(String, nullable=False, default="desktop")
    geo: Mapped[str | None] = mapped_column(String, nullable=True)
    page_id: Mapped[str | None] = mapped_column(String, nullable=True)
    cadence: Mapped[str] = mapped_column(String, nullable=False, default="daily")
    enabled: Mapped[bool] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_tracked_kw_tenant_site", "tenant_id", "site_id"),
        UniqueConstraint("tenant_id", "site_id", "keyword", "device", "geo",
                         name="uq_tracked_keyword"),
    )


# ---------------------------------------------------------------------------
# Reporting Engine (generated report artifacts)
# ---------------------------------------------------------------------------

class ReportArtifactRow(GrowthBase):
    """A generated report artifact (§4.6)."""

    __tablename__ = "growth_report_artifacts"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    organization_id: Mapped[str | None] = mapped_column(String, nullable=True)
    client_id: Mapped[str | None] = mapped_column(String, nullable=True)
    site_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    report_type: Mapped[str] = mapped_column(String, nullable=False)
    format: Mapped[str] = mapped_column(String, nullable=False, default="json")
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_report_artifact_tenant_site", "tenant_id", "site_id"),
    )


# ---------------------------------------------------------------------------
# Analytics Intelligence (append-only time series)
# ---------------------------------------------------------------------------

class AnalyticsSnapshotRow(GrowthBase):
    """Append-only analytics snapshot (time series, §4.8)."""

    __tablename__ = "growth_analytics_snapshots"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    organization_id: Mapped[str | None] = mapped_column(String, nullable=True)
    client_id: Mapped[str | None] = mapped_column(String, nullable=True)
    site_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)

    __table_args__ = (
        Index("ix_analytics_snapshot_tenant_site_time", "tenant_id", "site_id", "captured_at"),
    )


# ---------------------------------------------------------------------------
# Outreach (versioned sitewide report)
# ---------------------------------------------------------------------------

class OutreachReportRow(GrowthBase):
    """Append-only sitewide Outreach report (§4.9)."""

    __tablename__ = "growth_outreach_reports"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    organization_id: Mapped[str | None] = mapped_column(String, nullable=True)
    client_id: Mapped[str | None] = mapped_column(String, nullable=True)
    site_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_outreach_tenant_site_version", "tenant_id", "site_id", "version"),
    )


# ---------------------------------------------------------------------------
# Agency Management (organizational entities — CRUD, not versioned reports)
# ---------------------------------------------------------------------------

class OrganizationRow(GrowthBase):
    """An organization (the top-level tenant entity, §4.7, §3.5)."""

    __tablename__ = "growth_organizations"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    slug: Mapped[str] = mapped_column(String, nullable=True)
    branding_config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    settings: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class ClientRow(GrowthBase):
    """A client belonging to an organization (§4.7)."""

    __tablename__ = "growth_clients"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    organization_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    slug: Mapped[str] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class TeamRow(GrowthBase):
    """A team within an organization (§4.7)."""

    __tablename__ = "growth_teams"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    organization_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class WorkspaceRow(GrowthBase):
    """A saved UX context (§4.7) — purely a view/context configuration."""

    __tablename__ = "growth_workspaces"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    organization_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    client_id: Mapped[str | None] = mapped_column(String, nullable=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    created_by: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class TaskRow(GrowthBase):
    """A lightweight task referencing any engine finding/recommendation (§4.7)."""

    __tablename__ = "growth_tasks"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    organization_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    client_id: Mapped[str | None] = mapped_column(String, nullable=True)
    site_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    assignee_ref: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="open")
    priority: Mapped[str] = mapped_column(String, nullable=False, default="medium")
    reference_entity_type: Mapped[str | None] = mapped_column(String, nullable=True)
    reference_entity_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class NotificationRow(GrowthBase):
    """A notification (in-app delivery; email/SMS are interface-only, §4.7)."""

    __tablename__ = "growth_notifications"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    organization_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    recipient_ref: Mapped[str] = mapped_column(String, nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String, nullable=False, default="in_app")
    is_read: Mapped[bool] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    __table_args__ = (
        Index("ix_notification_recipient", "tenant_id", "recipient_ref", "is_read"),
    )


# ---------------------------------------------------------------------------
# Automation Engine (rules + execution log — CRUD)
# ---------------------------------------------------------------------------

class AutomationRuleRow(GrowthBase):
    """A persisted AutomationRule (§4.10)."""

    __tablename__ = "growth_automation_rules"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    organization_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    site_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    trigger_event_type: Mapped[str] = mapped_column(String, nullable=False, index=True)
    enabled: Mapped[bool] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)

    __table_args__ = (
        Index("ix_automation_rule_tenant_event", "tenant_id", "trigger_event_type"),
    )


class AutomationExecutionLogRow(GrowthBase):
    """Audit log for every automation rule firing (§4.10)."""

    __tablename__ = "growth_automation_execution_logs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    rule_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    site_id: Mapped[str | None] = mapped_column(String, nullable=True)
    result: Mapped[str] = mapped_column(String, nullable=False)
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)

    __table_args__ = (
        Index("ix_automation_exec_tenant_rule", "tenant_id", "rule_id"),
    )


# ---------------------------------------------------------------------------
# Provisioning helper
# ---------------------------------------------------------------------------

def create_growth_tables(engine: SAEngine) -> None:
    """Provision all Milestone 4 growth tables (GrowthBase only).

    Called once at startup by the composition root. Idempotent — ``checkfirst=True``
    is the default for ``create_all``.
    """
    GrowthBase.metadata.create_all(engine)
