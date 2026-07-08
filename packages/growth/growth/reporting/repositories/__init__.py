"""Reporting repositories."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from core.results import Err, Ok, Result
from growth.db import ReportArtifactRow
from growth.errors import GrowthStorageError
from growth.reporting.models import ReportArtifact
from intelligence.repositories._session import SessionMixin
from pydantic import TypeAdapter

__all__ = ["ReportingRepository"]


_artifact_adapter = TypeAdapter(ReportArtifact)


class ReportingRepository(SessionMixin):
    """Report artifact persistence using the GrowthBase report table."""

    def __init__(
        self,
        session_source: Session | sessionmaker[Session] | object,
        *,
        tenant_id: str | None = None,
    ) -> None:
        super().__init__(session_source, tenant_id=tenant_id)

    def save_artifact(
        self,
        artifact: ReportArtifact,
        org_id: str | None = None,
        client_id: str | None = None,
        site_id: str = "default",
        tenant_id: str | None = None,
    ) -> Result[ReportArtifact, GrowthStorageError]:
        tenant = self._resolve_tenant(tenant_id)
        try:
            with self._session() as session:
                session.add(ReportArtifactRow(
                    id=artifact.id,
                    tenant_id=tenant,
                    organization_id=org_id,
                    client_id=client_id,
                    site_id=site_id,
                    report_type=artifact.report_definition_ref,
                    format=artifact.format,
                    status="generated",
                    payload=_artifact_adapter.dump_python(artifact, mode="json"),
                    generated_at=artifact.generated_at,
                ))
            return Ok(artifact)
        except Exception as exc:  # noqa: BLE001
            return Err(GrowthStorageError(f"Failed to save report artifact: {exc}"))

    def get_artifact(self, artifact_id: str, tenant_id: str | None = None) -> Result[ReportArtifact | None, GrowthStorageError]:
        tenant = self._resolve_tenant(tenant_id)
        try:
            with self._session() as session:
                row = session.get(ReportArtifactRow, artifact_id)
                if row is None or row.tenant_id != tenant:
                    return Ok(None)
                return Ok(_artifact_adapter.validate_python(row.payload))
        except Exception as exc:  # noqa: BLE001
            return Err(GrowthStorageError(f"Failed to get report artifact: {exc}"))

    def list_artifacts(
        self,
        site_id: str,
        tenant_id: str | None = None,
    ) -> Result[list[ReportArtifact], GrowthStorageError]:
        tenant = self._resolve_tenant(tenant_id)
        try:
            with self._session() as session:
                rows = session.execute(
                    select(ReportArtifactRow).where(
                        ReportArtifactRow.tenant_id == tenant,
                        ReportArtifactRow.site_id == site_id,
                    ).order_by(ReportArtifactRow.generated_at.desc())
                ).scalars().all()
                return Ok([_artifact_adapter.validate_python(row.payload) for row in rows])
        except Exception as exc:  # noqa: BLE001
            return Err(GrowthStorageError(f"Failed to list report artifacts: {exc}"))