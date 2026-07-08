"""Intelligence relational schema — SQLAlchemy models (Milestone 2).

Deliberately on its **own** declarative ``Base``, separate from the Digital_Twin
``Base``, so the Milestone 1 migration-model-sync check (which autogenerates
against the Digital_Twin metadata only) is unaffected — this keeps Milestone 2
strictly additive to the Digital_Twin schema.

Three append-only tables, all tenant-scoped:

* ``knowledge_objects`` — one row per (page_id, version); the composed
  KnowledgeObject is stored as a JSON ``payload`` and reconstructed into the
  typed model at the repository boundary (never exposed as raw JSON to the
  domain).
* ``ai_invocations`` — the provider-agnostic audit record, raw response retained.
* ``page_snapshots`` — the crawl-time CrawledPage snapshot the analysis ran
  against, so re-analysis and versioning work without re-crawling.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

try:  # SQLAlchemy JSON type works on both SQLite and PostgreSQL
    from sqlalchemy import JSON
except ImportError:  # pragma: no cover
    JSON = Text  # type: ignore[assignment]

__all__ = [
    "IntelligenceBase",
    "KnowledgeObjectRow",
    "AIInvocationRow",
    "PageSnapshotRow",
]


class IntelligenceBase(DeclarativeBase):
    """Declarative base for the Milestone 2 intelligence tables (separate Base)."""


class KnowledgeObjectRow(IntelligenceBase):
    __tablename__ = "knowledge_objects"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    page_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    crawl_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)


class AIInvocationRow(IntelligenceBase):
    __tablename__ = "ai_invocations"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    page_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    capability: Mapped[str] = mapped_column(String, nullable=False)
    prompt_version: Mapped[str] = mapped_column(String, nullable=False)
    provider: Mapped[str] = mapped_column(String, nullable=False)
    model: Mapped[str] = mapped_column(String, nullable=False)
    cost_estimate: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    raw_response: Mapped[str] = mapped_column(Text, nullable=False, default="")
    validation_result: Mapped[str] = mapped_column(String, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)  # full AIInvocation
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class PageSnapshotRow(IntelligenceBase):
    __tablename__ = "page_snapshots"

    page_id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    url: Mapped[str] = mapped_column(String, nullable=False)
    crawl_id: Mapped[str | None] = mapped_column(String, nullable=True)
    crawled_page: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
