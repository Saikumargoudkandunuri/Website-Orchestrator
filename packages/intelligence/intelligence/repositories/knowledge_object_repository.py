"""Append-only, versioned KnowledgeObject persistence (§4.1).

Never overwrites a prior version: :meth:`next_version` returns ``max+1`` for a
page and :meth:`save` inserts a new row. The "current" object is the max-version
row (:meth:`get_latest`). The composed :class:`KnowledgeObject` is stored as a
JSON ``payload`` and reconstructed into the typed model at this boundary, so the
domain never sees raw JSON.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select

from intelligence.models.knowledge_object import KnowledgeObject
from intelligence.repositories._session import SessionMixin
from intelligence.repositories.models_orm import KnowledgeObjectRow

__all__ = ["VersionInfo", "KnowledgeObjectRepository"]


class VersionInfo:
    """Lightweight version-history entry (no full payload)."""

    __slots__ = ("version", "created_at", "crawl_id")

    def __init__(self, version: int, created_at: datetime, crawl_id: str | None) -> None:
        self.version = version
        self.created_at = created_at
        self.crawl_id = crawl_id


class KnowledgeObjectRepository(SessionMixin):
    """Persists and reads versioned KnowledgeObjects."""

    def next_version(self, tenant_id: str, page_id: str) -> int:
        """Return the next append-only version number for ``page_id`` (1-based)."""
        tenant = self._resolve_tenant(tenant_id)
        with self._session() as session:
            current = session.execute(
                select(func.max(KnowledgeObjectRow.version)).where(
                    KnowledgeObjectRow.tenant_id == tenant,
                    KnowledgeObjectRow.page_id == page_id,
                )
            ).scalar_one_or_none()
            return (current or 0) + 1

    def save(self, tenant_id: str, ko: KnowledgeObject) -> KnowledgeObject:
        """Insert ``ko`` as a new version row (append-only)."""
        tenant = self._resolve_tenant(tenant_id)
        stored = ko.model_copy(update={"tenant_id": tenant})
        with self._session() as session:
            session.add(
                KnowledgeObjectRow(
                    id=stored.id,
                    tenant_id=tenant,
                    page_id=stored.page_id,
                    version=stored.version,
                    crawl_id=stored.crawl_id,
                    created_at=stored.created_at,
                    payload=stored.model_dump(mode="json"),
                )
            )
        return stored

    def get_latest(self, tenant_id: str, page_id: str) -> KnowledgeObject | None:
        """Return the max-version KnowledgeObject for ``page_id``, or ``None``."""
        tenant = self._resolve_tenant(tenant_id)
        with self._session() as session:
            row = session.execute(
                select(KnowledgeObjectRow)
                .where(
                    KnowledgeObjectRow.tenant_id == tenant,
                    KnowledgeObjectRow.page_id == page_id,
                )
                .order_by(KnowledgeObjectRow.version.desc())
                .limit(1)
            ).scalar_one_or_none()
            return KnowledgeObject.model_validate(row.payload) if row else None

    def get_version(
        self, tenant_id: str, page_id: str, version: int
    ) -> KnowledgeObject | None:
        """Return a specific historical version, or ``None``."""
        tenant = self._resolve_tenant(tenant_id)
        with self._session() as session:
            row = session.execute(
                select(KnowledgeObjectRow).where(
                    KnowledgeObjectRow.tenant_id == tenant,
                    KnowledgeObjectRow.page_id == page_id,
                    KnowledgeObjectRow.version == version,
                )
            ).scalar_one_or_none()
            return KnowledgeObject.model_validate(row.payload) if row else None

    def list_versions(self, tenant_id: str, page_id: str) -> list[VersionInfo]:
        """Return version history (version, created_at, crawl_id), newest first."""
        tenant = self._resolve_tenant(tenant_id)
        with self._session() as session:
            rows = (
                session.execute(
                    select(
                        KnowledgeObjectRow.version,
                        KnowledgeObjectRow.created_at,
                        KnowledgeObjectRow.crawl_id,
                    )
                    .where(
                        KnowledgeObjectRow.tenant_id == tenant,
                        KnowledgeObjectRow.page_id == page_id,
                    )
                    .order_by(KnowledgeObjectRow.version.desc())
                )
                .all()
            )
            return [VersionInfo(v, c, cr) for (v, c, cr) in rows]
