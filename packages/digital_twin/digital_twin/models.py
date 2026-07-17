"""Digital_Twin relational schema — SQLAlchemy 2.x declarative models.

These models are the physical, relational representation of the crawled site
(Req 3.1): ``PAGES``, ``LINKS``, ``PAGE_METADATA``, ``ISSUES``,
``SUGGESTED_FIXES``, and ``AUDIT_TRAIL``. Storage is relational only — there is
no graph database and no embeddings in Milestone 0 (Req 3.7).

Multi-tenancy is designed in from day one: every table carries a **non-null**
``tenant_id`` column (Req 14.4). The column is indexed on every table because
all reads/writes are scoped to a single tenant.

The column set of each table mirrors the design's "Relational Schema
(Digital_Twin)" ER diagram exactly, and the string enum-ish columns
(``issue_type``, ``severity``, ``fix_type``, ``status``, ``transition``) store
the string values of the corresponding Core_Package enums in
:mod:`core.types`.
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
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

__all__ = [
    "Base",
    "Page",
    "Link",
    "PageMetadata",
    "Issue",
    "SuggestedFix",
    "AuditTrail",
]


class Base(DeclarativeBase):
    """Declarative base for all Digital_Twin ORM models.

    ``Base.metadata`` aggregates every table below and is the object Alembic
    targets for autogeneration and ``create_all``.
    """


class Page(Base):
    """A crawled page (Req 3.1, 3.2). ``crawled_at`` is a UTC timestamp used for
    the staleness decision (Req 3.4, 3.5)."""

    __tablename__ = "pages"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    url: Mapped[str] = mapped_column(String, nullable=False)
    final_url: Mapped[str | None] = mapped_column(String, nullable=True)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    word_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    has_schema: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    crawled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Milestone 4 — the editable-model fields. All nullable so existing rows and
    # the additive migration remain valid; JSON-shaped fields are stored as JSON
    # text to stay identical across SQLite and PostgreSQL.
    slug: Mapped[str | None] = mapped_column(String, nullable=True)
    canonical_url: Mapped[str | None] = mapped_column(String, nullable=True)
    headings: Mapped[str | None] = mapped_column(Text, nullable=True)
    schema_types: Mapped[str | None] = mapped_column(Text, nullable=True)
    wp_page_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    wp_post_type: Mapped[str | None] = mapped_column(String, nullable=True)

    links: Mapped[list[Link]] = relationship(
        back_populates="page", cascade="all, delete-orphan"
    )
    page_metadata: Mapped[list[PageMetadata]] = relationship(
        back_populates="page", cascade="all, delete-orphan"
    )
    issues: Mapped[list[Issue]] = relationship(
        back_populates="page", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_pages_tenant_url", "tenant_id", "url"),
    )


class Link(Base):
    """A link discovered on a page and its observed status (Req 2.3, 3.1)."""

    __tablename__ = "links"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    page_id: Mapped[str] = mapped_column(
        String, ForeignKey("pages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    href: Mapped[str] = mapped_column(String, nullable=False)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reachable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    redirect_chain_len: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    # Milestone 4 — the internal link graph. ``anchor_text``/``rel`` are captured
    # verbatim from the source HTML; ``is_internal`` marks same-domain links; and
    # ``to_page_id`` is the resolved destination page id (a plain reference,
    # populated after upsert by URL match — no DB-level FK so SQLite ADD COLUMN
    # stays safe). All nullable for a purely additive migration.
    anchor_text: Mapped[str | None] = mapped_column(String, nullable=True)
    rel: Mapped[str | None] = mapped_column(String, nullable=True)
    is_internal: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    to_page_id: Mapped[str | None] = mapped_column(String, nullable=True)

    page: Mapped[Page] = relationship(back_populates="links")


class PageMetadata(Base):
    """Per-page metadata; only the meta description is stored in M0 (Req 3.1)."""

    __tablename__ = "page_metadata"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    page_id: Mapped[str] = mapped_column(
        String, ForeignKey("pages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    meta_description: Mapped[str | None] = mapped_column(Text, nullable=True)

    page: Mapped[Page] = relationship(back_populates="page_metadata")


class Issue(Base):
    """A persisted issue candidate, which may be marked ignored (Req 4.11)."""

    __tablename__ = "issues"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    page_id: Mapped[str] = mapped_column(
        String, ForeignKey("pages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    issue_type: Mapped[str] = mapped_column(String, nullable=False)
    severity: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    ignored: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    page: Mapped[Page] = relationship(back_populates="issues")
    suggested_fixes: Mapped[list[SuggestedFix]] = relationship(
        back_populates="issue", cascade="all, delete-orphan"
    )


class SuggestedFix(Base):
    """A proposed change to resolve an Issue, carrying a governance status
    (Req 5.1, 8, 9)."""

    __tablename__ = "suggested_fixes"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    issue_id: Mapped[str] = mapped_column(
        String, ForeignKey("issues.id", ondelete="CASCADE"), nullable=False, index=True
    )
    fix_type: Mapped[str | None] = mapped_column(String, nullable=True)
    auto_applicable: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Persisted write target (Req 5.3, 11.5-11.8). A fix reloaded from the repo
    # must carry the media/page id it writes to, otherwise the Governance_Layer
    # cannot locate the live target when applying or rolling back an
    # auto-applicable fix. Both columns are nullable: a report-only fix has no
    # target, an alt-text fix carries ``target_media_id``, and a page-content
    # fix carries ``target_page_id``.
    target_media_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_page_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    proposed_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    # Milestone 1 — generation provenance for AI-produced fixes. Nullable so
    # heuristic/report-only fixes and existing Milestone 0 rows remain valid.
    generation_model: Mapped[str | None] = mapped_column(String, nullable=True)
    generation_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    issue: Mapped[Issue] = relationship(back_populates="suggested_fixes")
    audit_entries: Mapped[list[AuditTrail]] = relationship(
        back_populates="fix", cascade="all, delete-orphan"
    )


class AuditTrail(Base):
    """The single ordered log of every governance decision and transition
    (Req 9.3, 9.4). ``created_at`` is the UTC ordering key (Req 10.7)."""

    __tablename__ = "audit_trail"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    fix_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("suggested_fixes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    actor: Mapped[str] = mapped_column(String, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    transition: Mapped[str] = mapped_column(String, nullable=False)
    before_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    fix: Mapped[SuggestedFix] = relationship(back_populates="audit_entries")

    __table_args__ = (
        Index("ix_audit_trail_tenant_created", "tenant_id", "created_at"),
    )
