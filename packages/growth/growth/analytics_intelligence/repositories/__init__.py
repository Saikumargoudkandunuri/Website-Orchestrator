"""Analytics Intelligence repositories (§4.8)."""
from __future__ import annotations

from pydantic import TypeAdapter
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from core.results import Err, Ok, Result
from growth.analytics_intelligence.models import AnalyticsSnapshot
from growth.db import AnalyticsSnapshotRow
from growth.errors import GrowthStorageError
from intelligence.repositories._session import SessionMixin

__all__ = ["AnalyticsRepository"]


_snapshot_adapter = TypeAdapter(AnalyticsSnapshot)


class AnalyticsRepository(SessionMixin):
    """Append-only analytics snapshot persistence."""

    def __init__(
        self,
        session_source: Session | sessionmaker[Session] | object,
        *,
        tenant_id: str | None = None,
    ) -> None:
        super().__init__(session_source, tenant_id=tenant_id)

    def save_snapshots(
        self,
        snapshots: list[AnalyticsSnapshot],
        site_id: str,
        tenant_id: str | None = None,
    ) -> Result[None, GrowthStorageError]:
        tenant = self._resolve_tenant(tenant_id)
        try:
            with self._session() as session:
                for snapshot in snapshots:
                    if session.get(AnalyticsSnapshotRow, snapshot.snapshot_id) is not None:
                        continue
                    session.add(AnalyticsSnapshotRow(
                        id=snapshot.snapshot_id,
                        tenant_id=tenant,
                        site_id=site_id,
                        captured_at=snapshot.captured_at,
                        payload=_snapshot_adapter.dump_python(snapshot, mode="json"),
                    ))
            return Ok(None)
        except Exception as exc:  # noqa: BLE001
            return Err(GrowthStorageError(f"Failed to save analytics snapshots: {exc}"))

    def get_snapshots(
        self,
        site_id: str,
        tenant_id: str | None = None,
    ) -> Result[list[AnalyticsSnapshot], GrowthStorageError]:
        tenant = self._resolve_tenant(tenant_id)
        try:
            with self._session() as session:
                rows = session.execute(
                    select(AnalyticsSnapshotRow).where(
                        AnalyticsSnapshotRow.tenant_id == tenant,
                        AnalyticsSnapshotRow.site_id == site_id,
                    ).order_by(AnalyticsSnapshotRow.captured_at.asc())
                ).scalars().all()
                return Ok([_snapshot_adapter.validate_python(row.payload) for row in rows])
        except Exception as exc:  # noqa: BLE001
            return Err(GrowthStorageError(f"Failed to read analytics snapshots: {exc}"))