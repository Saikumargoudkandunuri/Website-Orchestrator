"""Generic append-only, versioned growth engine repository.

Growth engines inherit GrowthRepoMixin rather than duplicating next-version /
save / get-latest / list-versions logic. Mirrors Milestone 3's EngineRepoMixin
exactly, but lives in the growth package so M3 stays untouched.

Every new table in Milestone 4 carries organization_id and client_id in addition
to tenant_id and site_id (§3.5) for row-level tenant isolation.
"""
from __future__ import annotations
import uuid
from dataclasses import is_dataclass, replace
from datetime import datetime, timezone
from typing import Any
from sqlalchemy import func, select
from pydantic import TypeAdapter
from intelligence.repositories._session import SessionMixin

__all__ = ["GrowthRepoMixin"]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return uuid.uuid4().hex


def _dump_model(value: Any) -> dict[str, Any]:
    """Serialize Pydantic models and dataclasses into JSON-compatible dicts."""
    return TypeAdapter(type(value)).dump_python(value, mode="json")


def _load_model(model_class: type, payload: dict[str, Any]) -> Any:
    """Deserialize a JSON payload into either a Pydantic model or dataclass."""
    return TypeAdapter(model_class).validate_python(payload)


class GrowthRepoMixin(SessionMixin):
    """Generic versioned growth repository. Subclasses supply:
    - ``_row_class``: SQLAlchemy ORM row class.
    - ``_model_class``: Pydantic output model class.
    - ``_scope_col``: the scope column name ("page_id" or "site_id").
    """

    _row_class: type
    _model_class: type
    _scope_col: str

    def _row_scope(self, scope_value: str, tenant: str) -> Any:
        col = getattr(self._row_class, self._scope_col)
        return (self._row_class.tenant_id == tenant, col == scope_value)

    def next_version(self, tenant_id: str, scope_value: str) -> int:
        tenant = self._resolve_tenant(tenant_id)
        with self._session() as session:
            current = session.execute(
                select(func.max(self._row_class.version)).where(
                    *self._row_scope(scope_value, tenant)
                )
            ).scalar_one_or_none()
            return (current or 0) + 1

    def save(self, tenant_id: str, scope_value: str, report: Any, *,
             site_id: str | None = None, page_id: str | None = None,
             organization_id: str | None = None, client_id: str | None = None) -> Any:
        tenant = self._resolve_tenant(tenant_id)
        version = self.next_version(tenant_id, scope_value)
        if hasattr(report, "version"):
            if hasattr(report, "model_copy"):
                report = report.model_copy(update={"version": version})
            elif is_dataclass(report):
                report = replace(report, version=version)
        row = self._row_class(
            id=_new_id(), tenant_id=tenant, version=version,
            payload=_dump_model(report), computed_at=_utc_now(),
        )
        setattr(row, self._scope_col, scope_value)
        if site_id is not None and hasattr(row, "site_id") and self._scope_col != "site_id":
            row.site_id = site_id
        if page_id is not None and hasattr(row, "page_id") and self._scope_col != "page_id":
            row.page_id = page_id
        if organization_id is not None and hasattr(row, "organization_id"):
            row.organization_id = organization_id
        if client_id is not None and hasattr(row, "client_id"):
            row.client_id = client_id
        with self._session() as session:
            session.add(row)
        return report

    def get_latest(self, tenant_id: str, scope_value: str) -> Any | None:
        tenant = self._resolve_tenant(tenant_id)
        with self._session() as session:
            row = session.execute(
                select(self._row_class)
                .where(*self._row_scope(scope_value, tenant))
                .order_by(self._row_class.version.desc())
                .limit(1)
            ).scalar_one_or_none()
            return _load_model(self._model_class, row.payload) if row else None

    def get_version(self, tenant_id: str, scope_value: str, version: int) -> Any | None:
        tenant = self._resolve_tenant(tenant_id)
        with self._session() as session:
            row = session.execute(
                select(self._row_class).where(
                    *self._row_scope(scope_value, tenant),
                    self._row_class.version == version,
                )
            ).scalar_one_or_none()
            return _load_model(self._model_class, row.payload) if row else None

    def list_versions(self, tenant_id: str, scope_value: str) -> list[dict[str, Any]]:
        tenant = self._resolve_tenant(tenant_id)
        with self._session() as session:
            rows = session.execute(
                select(self._row_class.version, self._row_class.computed_at)
                .where(*self._row_scope(scope_value, tenant))
                .order_by(self._row_class.version.desc())
            ).all()
            return [{"version": v, "computed_at": c} for (v, c) in rows]
