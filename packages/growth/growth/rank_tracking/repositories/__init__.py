"""Rank Tracking repositories."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import TypeAdapter
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from core.results import Err, Ok, Result
from growth.db import RankTrackingSnapshotRow, TrackedKeywordRow
from growth.errors import GrowthStorageError
from growth.rank_tracking.models import RankingSnapshot, TrackedKeyword
from intelligence.repositories._session import SessionMixin

__all__ = ["RankTrackingRepository"]


_keyword_adapter = TypeAdapter(TrackedKeyword)
_snapshot_adapter = TypeAdapter(RankingSnapshot)


class RankTrackingRepository(SessionMixin):
    """Append-only rank snapshot storage plus tracked-keyword configuration."""

    def __init__(
        self,
        session_source: Session | sessionmaker[Session] | object,
        *,
        tenant_id: str | None = None,
    ) -> None:
        super().__init__(session_source, tenant_id=tenant_id)

    def save_tracked_keyword(
        self,
        keyword: TrackedKeyword,
        org_id: str | None = None,
        client_id: str | None = None,
        site_id: str | None = None,
        tenant_id: str | None = None,
    ) -> Result[TrackedKeyword, GrowthStorageError]:
        """Insert or update a tracked keyword without leaking across tenants."""
        tenant = self._resolve_tenant(tenant_id)
        try:
            with self._session() as session:
                row = session.get(TrackedKeywordRow, keyword.keyword_id)
                if row is None:
                    row = TrackedKeywordRow(
                        id=keyword.keyword_id,
                        tenant_id=tenant,
                        organization_id=org_id,
                        client_id=client_id,
                        site_id=site_id or keyword.page_id,
                        keyword=keyword.keyword,
                        device=keyword.device,
                        geo=keyword.geo,
                        page_id=keyword.page_id,
                        cadence=keyword.cadence,
                        enabled=1 if keyword.active else 0,
                        created_at=datetime.now(timezone.utc),
                    )
                    session.add(row)
                else:
                    row.keyword = keyword.keyword
                    row.page_id = keyword.page_id
                    row.device = keyword.device
                    row.geo = keyword.geo
                    row.cadence = keyword.cadence
                    row.enabled = 1 if keyword.active else 0
                    if site_id is not None:
                        row.site_id = site_id
                    if org_id is not None:
                        row.organization_id = org_id
                    if client_id is not None:
                        row.client_id = client_id
            return Ok(keyword)
        except Exception as exc:  # noqa: BLE001
            return Err(GrowthStorageError(f"Failed to save tracked keyword: {exc}"))

    def get_tracked_keywords(
        self,
        site_id: str,
        active_only: bool = False,
        tenant_id: str | None = None,
    ) -> Result[list[TrackedKeyword], GrowthStorageError]:
        """Return tracked keywords for a single tenant/site."""
        tenant = self._resolve_tenant(tenant_id)
        try:
            with self._session() as session:
                stmt = select(TrackedKeywordRow).where(
                    TrackedKeywordRow.tenant_id == tenant,
                    TrackedKeywordRow.site_id == site_id,
                )
                if active_only:
                    stmt = stmt.where(TrackedKeywordRow.enabled == 1)
                rows = session.execute(stmt).scalars().all()
                return Ok([
                    TrackedKeyword(
                        keyword_id=row.id,
                        keyword=row.keyword,
                        page_id=row.page_id or "",
                        device=row.device,
                        geo=row.geo or "",
                        cadence=row.cadence,
                        active=bool(row.enabled),
                    )
                    for row in rows
                ])
        except Exception as exc:  # noqa: BLE001
            return Err(GrowthStorageError(f"Failed to get tracked keywords: {exc}"))

    def save_snapshots(
        self,
        snapshots: list[RankingSnapshot],
        site_id: str,
        tenant_id: str | None = None,
        organization_id: str | None = None,
        client_id: str | None = None,
    ) -> Result[None, GrowthStorageError]:
        """Append ranking snapshots idempotently by snapshot id."""
        tenant = self._resolve_tenant(tenant_id)
        try:
            with self._session() as session:
                for snapshot in snapshots:
                    if session.get(RankTrackingSnapshotRow, snapshot.snapshot_id) is not None:
                        continue
                    row = RankTrackingSnapshotRow(
                        id=snapshot.snapshot_id,
                        tenant_id=tenant,
                        organization_id=organization_id,
                        client_id=client_id,
                        site_id=site_id,
                        page_id=snapshot.page_id,
                        keyword=snapshot.keyword,
                        device=snapshot.device,
                        geo=snapshot.geo,
                        captured_at=snapshot.captured_at,
                        payload=_snapshot_adapter.dump_python(snapshot, mode="json"),
                    )
                    session.add(row)
            return Ok(None)
        except Exception as exc:  # noqa: BLE001
            return Err(GrowthStorageError(f"Failed to save snapshots: {exc}"))

    def get_snapshots(
        self,
        site_id: str,
        keyword_id: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        tenant_id: str | None = None,
    ) -> Result[list[RankingSnapshot], GrowthStorageError]:
        """Read ranking snapshots for reporting and trend generation."""
        tenant = self._resolve_tenant(tenant_id)
        try:
            with self._session() as session:
                stmt = select(RankTrackingSnapshotRow).where(
                    RankTrackingSnapshotRow.tenant_id == tenant,
                    RankTrackingSnapshotRow.site_id == site_id,
                )
                if start_date is not None:
                    stmt = stmt.where(RankTrackingSnapshotRow.captured_at >= start_date)
                if end_date is not None:
                    stmt = stmt.where(RankTrackingSnapshotRow.captured_at <= end_date)
                rows = session.execute(stmt.order_by(RankTrackingSnapshotRow.captured_at.asc())).scalars().all()
                snapshots = [_snapshot_adapter.validate_python(row.payload) for row in rows]
                if keyword_id is not None:
                    snapshots = [s for s in snapshots if s.keyword_id == keyword_id]
                return Ok(snapshots)
        except Exception as exc:  # noqa: BLE001
            return Err(GrowthStorageError(f"Failed to get snapshots: {exc}"))

    def get_latest_snapshot(
        self,
        keyword_id: str,
        site_id: str | None = None,
        tenant_id: str | None = None,
    ) -> Result[RankingSnapshot | None, GrowthStorageError]:
        """Return the newest snapshot for one keyword configuration."""
        tenant = self._resolve_tenant(tenant_id)
        try:
            with self._session() as session:
                stmt = select(RankTrackingSnapshotRow).where(RankTrackingSnapshotRow.tenant_id == tenant)
                if site_id is not None:
                    stmt = stmt.where(RankTrackingSnapshotRow.site_id == site_id)
                rows = session.execute(stmt.order_by(RankTrackingSnapshotRow.captured_at.desc())).scalars().all()
                for row in rows:
                    snapshot = _snapshot_adapter.validate_python(row.payload)
                    if snapshot.keyword_id == keyword_id:
                        return Ok(snapshot)
                return Ok(None)
        except Exception as exc:  # noqa: BLE001
            return Err(GrowthStorageError(f"Failed to get latest snapshot: {exc}"))