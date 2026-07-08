"""Enterprise Repositories for System 2."""

from __future__ import annotations

from typing import Any
from sqlalchemy import select

from intelligence.repositories._session import SessionMixin
from saas.enterprise.models import (
    UserRoleAssignmentRow,
    AuditTrailRecordRow,
    UserRoleAssignment,
    AuditTrailRecord,
)

__all__ = ["EnterpriseRepository"]


class EnterpriseRepository(SessionMixin):
    """SaaS Enterprise Repository managing role mappings and audit trails."""

    def save_role(self, assignment: UserRoleAssignment) -> None:
        tenant = self._resolve_tenant(assignment.tenant_id)
        with self._session() as session:
            existing = session.execute(
                select(UserRoleAssignmentRow).where(
                    UserRoleAssignmentRow.tenant_id == tenant,
                    UserRoleAssignmentRow.user_id == assignment.user_id,
                )
            ).scalar_one_or_none()

            if existing:
                existing.role = assignment.role
            else:
                session.add(UserRoleAssignmentRow(
                    id=assignment.id,
                    tenant_id=tenant,
                    user_id=assignment.user_id,
                    role=assignment.role,
                ))
            session.commit()

    def get_user_role(self, tenant_id: str, user_id: str) -> str | None:
        tenant = self._resolve_tenant(tenant_id)
        with self._session() as session:
            row = session.execute(
                select(UserRoleAssignmentRow).where(
                    UserRoleAssignmentRow.tenant_id == tenant,
                    UserRoleAssignmentRow.user_id == user_id,
                )
            ).scalar_one_or_none()
            return row.role if row else None

    def save_audit(self, record: AuditTrailRecord) -> None:
        tenant = self._resolve_tenant(record.tenant_id)
        with self._session() as session:
            session.add(AuditTrailRecordRow(
                id=record.id,
                tenant_id=tenant,
                actor=record.actor,
                action=record.action,
                target_id=record.target_id,
                changes_json=record.changes_json,
                signature=record.signature,
                created_at=record.created_at,
            ))
            session.commit()

    def list_audits(self, tenant_id: str) -> list[AuditTrailRecord]:
        tenant = self._resolve_tenant(tenant_id)
        with self._session() as session:
            rows = session.execute(
                select(AuditTrailRecordRow).where(
                    AuditTrailRecordRow.tenant_id == tenant
                ).order_by(AuditTrailRecordRow.created_at.desc())
            ).scalars().all()
            return [
                AuditTrailRecord(
                    id=r.id,
                    tenant_id=r.tenant_id,
                    actor=r.actor,
                    action=r.action,
                    target_id=r.target_id,
                    changes_json=r.changes_json,
                    signature=r.signature,
                    created_at=r.created_at,
                )
                for r in rows
            ]
