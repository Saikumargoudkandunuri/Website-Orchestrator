"""Onboarding relational schema — SQLAlchemy 2.x declarative models.

These models back the Foundation sub-project: the workspace/project/website/
connection hierarchy plus the discovered integrations, website groups, and the
onboarding audit trail.

Multi-tenancy is designed in from day one: every table carries a **non-null**
``tenant_id`` column, indexed on every table because all reads/writes are scoped
to a single tenant (mirrors the Digital_Twin schema convention).

The column set reflects the enterprise architecture review:

* ``websites`` carries ``environment``, ``status``, ``website_type``, full
  detection output (CMS, builder, theme, plugins, server, hosting, versions),
  and the per-website ``agent_config`` (independent AI configuration).
* ``connections`` carries ``connection_type`` (CMS-agnostic) and stores only an
  encrypted credential blob plus a JSON ``capabilities`` document.
* ``integrations`` is a first-class table (not JSON) so sync times, refresh
  tokens, quotas, and errors are queryable columns.
* ``website_groups`` supports grouping websites (e.g. a "Production" group).
* ``onboarding_audit`` records every onboarding/AI action with who/why/before/
  after/rollback/approval/cost metadata.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

__all__ = [
    "Base",
    "Workspace",
    "Project",
    "WebsiteGroup",
    "Website",
    "Connection",
    "Integration",
    "OnboardingAudit",
]


class Base(DeclarativeBase):
    """Declarative base for all Onboarding ORM models."""


class Workspace(Base):
    """A top-level tenant-scoped workspace (the onboarding root)."""

    __tablename__ = "workspaces"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    projects: Mapped[list[Project]] = relationship(
        back_populates="workspace", cascade="all, delete-orphan"
    )


class Project(Base):
    """A project inside a workspace (groups websites by initiative)."""

    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    workspace_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    workspace: Mapped[Workspace] = relationship(back_populates="projects")
    websites: Mapped[list[Website]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class WebsiteGroup(Base):
    """A named group of websites within a project (e.g. "Production")."""

    __tablename__ = "website_groups"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    websites: Mapped[list[Website]] = relationship(
        back_populates="group", cascade="all, delete-orphan"
    )


class Website(Base):
    """A website: detection output, lifecycle status, and per-site AI config.

    Everything the WebsiteDetector discovers is stored here so the dashboard and
    AI agents have a single source of truth per website.
    """

    __tablename__ = "websites"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    workspace_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    project_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    group_id: Mapped[str | None] = mapped_column(
        String,
        ForeignKey("website_groups.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Identity
    name: Mapped[str] = mapped_column(String, nullable=False)
    url: Mapped[str] = mapped_column(String, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String, nullable=True)

    # Lifecycle (architecture review #1, #2)
    environment: Mapped[str] = mapped_column(String, nullable=False, default="production")
    status: Mapped[str] = mapped_column(String, nullable=False, default="CONNECTED")
    website_type: Mapped[str] = mapped_column(
        String, nullable=False, default="unknown"
    )

    # Detection output (architecture review #5, #6, #7, #15)
    cms: Mapped[str | None] = mapped_column(String, nullable=True)
    builder: Mapped[str | None] = mapped_column(String, nullable=True)
    builder_version: Mapped[str | None] = mapped_column(String, nullable=True)
    theme: Mapped[str | None] = mapped_column(String, nullable=True)
    theme_version: Mapped[str | None] = mapped_column(String, nullable=True)
    parent_theme: Mapped[str | None] = mapped_column(String, nullable=True)
    child_theme: Mapped[str | None] = mapped_column(String, nullable=True)
    framework: Mapped[str | None] = mapped_column(String, nullable=True)
    wordpress_version: Mapped[str | None] = mapped_column(String, nullable=True)
    php_version: Mapped[str | None] = mapped_column(String, nullable=True)
    server: Mapped[str | None] = mapped_column(String, nullable=True)
    hosting: Mapped[str | None] = mapped_column(String, nullable=True)
    cdn: Mapped[str | None] = mapped_column(String, nullable=True)
    waf: Mapped[str | None] = mapped_column(String, nullable=True)

    # Detection signals
    rest_api_available: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    has_robots_txt: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    has_sitemap: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    has_rss: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    has_opengraph: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    has_schema: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    has_canonical: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    has_hreflang: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Plugins (architecture review #5) — stored as JSON lists of plugin records
    plugins: Mapped[list | None] = mapped_column(JSON, nullable=True)
    seo_plugins: Mapped[list | None] = mapped_column(JSON, nullable=True)
    cache_plugins: Mapped[list | None] = mapped_column(JSON, nullable=True)
    commerce_plugins: Mapped[list | None] = mapped_column(JSON, nullable=True)
    analytics_plugins: Mapped[list | None] = mapped_column(JSON, nullable=True)
    security_plugins: Mapped[list | None] = mapped_column(JSON, nullable=True)
    forms_plugins: Mapped[list | None] = mapped_column(JSON, nullable=True)
    membership_plugins: Mapped[list | None] = mapped_column(JSON, nullable=True)
    performance_plugins: Mapped[list | None] = mapped_column(JSON, nullable=True)
    language_plugins: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Detection confidence (architecture review #7)
    detection_confidence: Mapped[str] = mapped_column(
        String, nullable=False, default="low"
    )

    # Per-website AI configuration (architecture review #8)
    agent_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Feature flags
    ai_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    automation_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    memory_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    approval_mode: Mapped[str] = mapped_column(
        String, nullable=False, default="human"
    )

    # Onboarding lifecycle state (state_machine.py)
    onboarding_state: Mapped[str] = mapped_column(
        String, nullable=False, default="created"
    )
    last_crawled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    workspace: Mapped[Workspace] = relationship()
    project: Mapped[Project] = relationship(back_populates="websites")
    group: Mapped[WebsiteGroup | None] = relationship(back_populates="websites")
    connections: Mapped[list[Connection]] = relationship(
        back_populates="website", cascade="all, delete-orphan"
    )
    integrations: Mapped[list[Integration]] = relationship(
        back_populates="website", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_websites_tenant_url", "tenant_id", "url"),
    )


class Connection(Base):
    """A connection to a website via a CMS-agnostic method (architecture review #3).

    Only an encrypted credential blob is stored; the plaintext credential never
    touches the database. ``capabilities`` is a JSON document of detected
    permissions/limits.
    """

    __tablename__ = "connections"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    website_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("websites.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    connection_type: Mapped[str] = mapped_column(
        String, nullable=False, default="wordpress_rest"
    )
    # Encrypted credential blob (never plaintext).
    encrypted_credentials: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Non-secret connection metadata (username, base url, etc.) as JSON.
    connection_meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Detected capabilities/permissions/limits (architecture review: Capabilities).
    capabilities: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    website: Mapped[Website] = relationship(back_populates="connections")


class Integration(Base):
    """A discovered integration (architecture review #4) — first-class table.

    JSON-in-a-column would make sync times, refresh tokens, quotas, and errors
    painful to query, so each becomes a column.
    """

    __tablename__ = "integrations"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    website_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("websites.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="discovered")
    last_sync: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Encrypted refresh/access token blob (never plaintext).
    encrypted_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    quota_used: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quota_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    integration_meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    website: Mapped[Website] = relationship(back_populates="integrations")


class OnboardingAudit(Base):
    """Audit trail for every onboarding/AI action (architecture review #13)."""

    __tablename__ = "onboarding_audit"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    website_id: Mapped[str | None] = mapped_column(
        String,
        ForeignKey("websites.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    actor_type: Mapped[str] = mapped_column(String, nullable=False)  # ai_agent | human | workflow
    actor_id: Mapped[str] = mapped_column(String, nullable=False)
    action: Mapped[str] = mapped_column(String, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    before_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    after_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    rollback_available: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    approval_required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    execution_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tokens_used: Mapped[int | None] = mapped_column(Integer, nullable=True)
    model: Mapped[str | None] = mapped_column(String, nullable=True)
    cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    website: Mapped[Website | None] = relationship()
