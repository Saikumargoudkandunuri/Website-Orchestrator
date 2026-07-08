"""Generic append-only, versioned engine repository (Milestone 3 §4.1 pattern).

Every engine's repository inherits :class:`EngineRepoMixin` rather than
duplicating the next-version / save / get-latest / list-versions logic ten
times.  The mixin only knows about an ORM row class, a Pydantic model class,
and a scope key (``page_id`` or ``site_id`` depending on the engine) — all
other logic is identical across all ten engines, exactly as
:class:`~intelligence.repositories.knowledge_object_repository.KnowledgeObjectRepository`
is the single pattern for Milestone 2's versioned records.

The design follows Milestone 2's session/tenant plumbing exactly:
- Session management is provided by
  :class:`~intelligence.repositories._session.SessionMixin`.
- Tenant isolation is enforced via ``_resolve_tenant()``.
- Raw JSON ``payload`` is stored on write, Pydantic ``model_validate`` on read.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, TypeVar

from sqlalchemy import func, select
from sqlalchemy.orm import DeclarativeBase

# Reuse M2's session plumbing directly — no reimplementation.
from intelligence.repositories._session import SessionMixin

__all__ = ["EngineRepoMixin"]

_RowT = TypeVar("_RowT")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return uuid.uuid4().hex


class EngineRepoMixin(SessionMixin):
    """Generic versioned engine repository shared by all ten engines.

    Subclasses supply:
    - ``_row_class``: the SQLAlchemy ORM row class.
    - ``_model_class``: the Pydantic output model class.
    - ``_scope_col``: the name of the scope column (``"page_id"`` or
      ``"site_id"``).

    All CRUD is then handled here; the concrete repositories only add
    convenience constructors or, in rare cases, extra query methods.
    """

    _row_class: type  # SQLAlchemy ORM row
    _model_class: type  # Pydantic model
    _scope_col: str    # "page_id" or "site_id"

    def _row_scope(self, scope_value: str, tenant: str) -> Any:
        """Build the WHERE clauses scoping to tenant + scope value."""
        col = getattr(self._row_class, self._scope_col)
        return (self._row_class.tenant_id == tenant, col == scope_value)

    def next_version(self, tenant_id: str, scope_value: str) -> int:
        """Return the next append-only version number (1-based)."""
        tenant = self._resolve_tenant(tenant_id)
        with self._session() as session:
            current = session.execute(
                select(func.max(self._row_class.version)).where(
                    *self._row_scope(scope_value, tenant)
                )
            ).scalar_one_or_none()
            return (current or 0) + 1

    def save(
        self,
        tenant_id: str,
        scope_value: str,
        report: Any,
        *,
        site_id: str | None = None,
        page_id: str | None = None,
    ) -> Any:
        """Insert ``report`` as a new version row (append-only).

        Returns the report with its ``version`` field updated to the assigned
        version number so callers can rely on ``saved.version`` being accurate.
        """
        tenant = self._resolve_tenant(tenant_id)
        version = self.next_version(tenant_id, scope_value)
        # Stamp the version on the report so the returned value and the stored
        # payload both carry the correct version number.
        if hasattr(report, "version"):
            report = report.model_copy(update={"version": version})
        row = self._row_class(
            id=_new_id(),
            tenant_id=tenant,
            version=version,
            payload=report.model_dump(mode="json"),
            computed_at=_utc_now(),
        )
        # Set the scope column dynamically.
        setattr(row, self._scope_col, scope_value)
        # Some tables also carry a secondary scope (e.g., page_id on a sitewide row).
        if site_id is not None and hasattr(row, "site_id") and self._scope_col != "site_id":
            row.site_id = site_id
        if page_id is not None and hasattr(row, "page_id") and self._scope_col != "page_id":
            row.page_id = page_id
        with self._session() as session:
            session.add(row)
        return report

    def get_latest(self, tenant_id: str, scope_value: str) -> Any | None:
        """Return the max-version report for ``scope_value``, or ``None``."""
        tenant = self._resolve_tenant(tenant_id)
        with self._session() as session:
            row = session.execute(
                select(self._row_class)
                .where(*self._row_scope(scope_value, tenant))
                .order_by(self._row_class.version.desc())
                .limit(1)
            ).scalar_one_or_none()
            return self._model_class.model_validate(row.payload) if row else None

    def get_version(
        self, tenant_id: str, scope_value: str, version: int
    ) -> Any | None:
        """Return a specific historical version, or ``None``."""
        tenant = self._resolve_tenant(tenant_id)
        with self._session() as session:
            row = session.execute(
                select(self._row_class).where(
                    *self._row_scope(scope_value, tenant),
                    self._row_class.version == version,
                )
            ).scalar_one_or_none()
            return self._model_class.model_validate(row.payload) if row else None

    def list_versions(
        self, tenant_id: str, scope_value: str
    ) -> list[dict[str, Any]]:
        """Return version history [{version, computed_at}], newest first."""
        tenant = self._resolve_tenant(tenant_id)
        with self._session() as session:
            rows = session.execute(
                select(
                    self._row_class.version,
                    self._row_class.computed_at,
                )
                .where(*self._row_scope(scope_value, tenant))
                .order_by(self._row_class.version.desc())
            ).all()
            return [{"version": v, "computed_at": c} for (v, c) in rows]
