"""AuditJob repository — lifecycle management for full sitewide audits (§6, §9).

Unlike the engine output repositories, AuditJob rows are mutable (the orchestrator
updates ``status``, ``engines_completed``, ``engines_failed``, etc. as the job
progresses) rather than append-only. They are still tenant-scoped and indexed on
``site_id``.

Status transitions:
  ``pending`` → ``running`` → ``completed`` | ``partial`` | ``failed``
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from engines.shared.db import AuditJobRow
from intelligence.repositories._session import SessionMixin

__all__ = ["AuditJobStatus", "AuditJob", "AuditJobRepository"]


class AuditJobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"    # some engines failed, others succeeded
    FAILED = "failed"      # all engines failed or a critical error occurred


class AuditJob:
    """In-memory representation of a running or completed audit job."""

    __slots__ = (
        "id", "tenant_id", "site_id", "status",
        "engines_requested", "engines_completed", "engines_failed",
        "started_at", "completed_at", "result_summary", "created_at",
    )

    def __init__(
        self,
        id: str,
        tenant_id: str,
        site_id: str,
        status: AuditJobStatus,
        engines_requested: list[str],
        engines_completed: list[str],
        engines_failed: list[str],
        started_at: datetime | None,
        completed_at: datetime | None,
        result_summary: dict,
        created_at: datetime,
    ) -> None:
        self.id = id
        self.tenant_id = tenant_id
        self.site_id = site_id
        self.status = status
        self.engines_requested = engines_requested
        self.engines_completed = engines_completed
        self.engines_failed = engines_failed
        self.started_at = started_at
        self.completed_at = completed_at
        self.result_summary = result_summary
        self.created_at = created_at


def _job_from_row(row: AuditJobRow) -> AuditJob:
    return AuditJob(
        id=row.id,
        tenant_id=row.tenant_id,
        site_id=row.site_id,
        status=AuditJobStatus(row.status),
        engines_requested=list(row.engines_requested or []),
        engines_completed=list(row.engines_completed or []),
        engines_failed=list(row.engines_failed or []),
        started_at=row.started_at,
        completed_at=row.completed_at,
        result_summary=dict(row.result_summary or {}),
        created_at=row.created_at,
    )


class AuditJobRepository(SessionMixin):
    """CRUD for audit job lifecycle tracking."""

    def create(
        self,
        tenant_id: str,
        site_id: str,
        engines_requested: list[str],
    ) -> AuditJob:
        tenant = self._resolve_tenant(tenant_id)
        now = datetime.now(timezone.utc)
        job_id = uuid.uuid4().hex
        row = AuditJobRow(
            id=job_id,
            tenant_id=tenant,
            site_id=site_id,
            status=AuditJobStatus.PENDING.value,
            engines_requested=list(engines_requested),
            engines_completed=[],
            engines_failed=[],
            started_at=None,
            completed_at=None,
            result_summary={},
            created_at=now,
        )
        with self._session() as session:
            session.add(row)
        return _job_from_row(row)

    def get(self, tenant_id: str, job_id: str) -> AuditJob | None:
        tenant = self._resolve_tenant(tenant_id)
        with self._session() as session:
            row = session.execute(
                select(AuditJobRow).where(
                    AuditJobRow.id == job_id,
                    AuditJobRow.tenant_id == tenant,
                )
            ).scalar_one_or_none()
            return _job_from_row(row) if row else None

    def list_for_site(self, tenant_id: str, site_id: str) -> list[AuditJob]:
        tenant = self._resolve_tenant(tenant_id)
        with self._session() as session:
            rows = session.execute(
                select(AuditJobRow)
                .where(
                    AuditJobRow.tenant_id == tenant,
                    AuditJobRow.site_id == site_id,
                )
                .order_by(AuditJobRow.created_at.desc())
            ).scalars().all()
            return [_job_from_row(r) for r in rows]

    def mark_running(self, tenant_id: str, job_id: str) -> AuditJob:
        return self._update_status(
            tenant_id, job_id,
            status=AuditJobStatus.RUNNING,
            started_at=datetime.now(timezone.utc),
        )

    def mark_engine_complete(
        self, tenant_id: str, job_id: str, engine_name: str
    ) -> AuditJob:
        tenant = self._resolve_tenant(tenant_id)
        with self._session() as session:
            row = self._get_row(session, tenant, job_id)
            completed = list(row.engines_completed or [])
            if engine_name not in completed:
                completed.append(engine_name)
            row.engines_completed = completed
            session.flush()
            return _job_from_row(row)

    def mark_engine_failed(
        self, tenant_id: str, job_id: str, engine_name: str
    ) -> AuditJob:
        tenant = self._resolve_tenant(tenant_id)
        with self._session() as session:
            row = self._get_row(session, tenant, job_id)
            failed = list(row.engines_failed or [])
            if engine_name not in failed:
                failed.append(engine_name)
            row.engines_failed = failed
            session.flush()
            return _job_from_row(row)

    def mark_finished(
        self,
        tenant_id: str,
        job_id: str,
        result_summary: dict,
    ) -> AuditJob:
        """Transition to completed/partial/failed based on engine outcomes."""
        tenant = self._resolve_tenant(tenant_id)
        with self._session() as session:
            row = self._get_row(session, tenant, job_id)
            completed = list(row.engines_completed or [])
            failed = list(row.engines_failed or [])
            requested = list(row.engines_requested or [])
            if not failed:
                final_status = AuditJobStatus.COMPLETED
            elif completed:
                final_status = AuditJobStatus.PARTIAL
            else:
                final_status = AuditJobStatus.FAILED
            row.status = final_status.value
            row.completed_at = datetime.now(timezone.utc)
            row.result_summary = result_summary
            session.flush()
            return _job_from_row(row)

    # --- Helpers -------------------------------------------------------------

    def _update_status(
        self,
        tenant_id: str,
        job_id: str,
        *,
        status: AuditJobStatus,
        started_at: datetime | None = None,
    ) -> AuditJob:
        tenant = self._resolve_tenant(tenant_id)
        with self._session() as session:
            row = self._get_row(session, tenant, job_id)
            row.status = status.value
            if started_at is not None:
                row.started_at = started_at
            session.flush()
            return _job_from_row(row)

    @staticmethod
    def _get_row(session: Session, tenant: str, job_id: str) -> AuditJobRow:
        from engines.errors import EngineStorageError

        row = session.execute(
            select(AuditJobRow).where(
                AuditJobRow.id == job_id,
                AuditJobRow.tenant_id == tenant,
            )
        ).scalar_one_or_none()
        if row is None:
            raise EngineStorageError(f"AuditJob {job_id!r} not found for tenant {tenant!r}")
        return row
