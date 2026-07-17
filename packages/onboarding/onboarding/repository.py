"""Onboarding repository — persistence for the onboarding hierarchy.

A thin SQLAlchemy-backed repository scoped to a single tenant (mirrors the
Digital_Twin repository conventions). It owns the workspace/project/website/
connection/integration/audit rows and exposes typed read/write helpers used by
the onboarding services.

Multi-tenancy invariants: every write is stamped with the resolved tenant_id;
a write with no resolvable tenant is rejected (Req 14.5, 14.6).
"""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from core.exceptions import OrchestratorError

from onboarding.models import (
    Connection,
    Integration,
    OnboardingAudit,
    Project,
    Website,
    WebsiteGroup,
    Workspace,
)

__all__ = ["OnboardingRepository", "_new_id"]


def _new_id() -> str:
    """Return a fresh opaque identifier for a persisted row."""
    return uuid.uuid4().hex


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class OnboardingRepository:
    """Tenant-scoped persistence for onboarding resources."""

    def __init__(
        self,
        session_source: Session | sessionmaker[Session] | object,
        *,
        tenant_id: str | None = None,
    ) -> None:
        self._session_source = session_source
        self._configured_tenant = tenant_id

    # --- Session / tenant plumbing -------------------------------------------

    @contextmanager
    def _session(self) -> Iterator[Session]:
        external = isinstance(self._session_source, Session)
        session: Session = (
            self._session_source  # type: ignore[assignment]
            if external
            else self._session_source()  # type: ignore[operator]
        )
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            if not external:
                session.close()

    def _resolve_tenant(self, tenant_id: str | None) -> str:
        for candidate in (tenant_id, self._configured_tenant):
            if candidate is None:
                continue
            resolved = str(candidate).strip()
            if resolved:
                return resolved
        raise OrchestratorError(
            "Cannot resolve a tenant_id for the write: no tenant was provided "
            "and none is configured."
        )

    # --- Workspace ------------------------------------------------------------

    def create_workspace(
        self, tenant_id: str, *, name: str, description: str | None
    ) -> Workspace:
        tenant = self._resolve_tenant(tenant_id)
        now = _utcnow()
        row = Workspace(
            id=_new_id(),
            tenant_id=tenant,
            name=name,
            description=description,
            is_active=True,
            created_at=now,
        )
        with self._session() as session:
            session.add(row)
            session.flush()
            session.refresh(row)
            return row

    def get_workspace(self, tenant_id: str, workspace_id: str) -> Workspace | None:
        tenant = self._resolve_tenant(tenant_id)
        with self._session() as session:
            return session.execute(
                select(Workspace).where(
                    Workspace.id == workspace_id,
                    Workspace.tenant_id == tenant,
                )
            ).scalar_one_or_none()

    def list_workspaces(self, tenant_id: str) -> list[Workspace]:
        with self._session() as session:
            return list(
                session.execute(
                    select(Workspace).where(Workspace.tenant_id == tenant_id)
                ).scalars()
            )

    def update_workspace(
        self, tenant_id: str, workspace_id: str, **changes: object
    ) -> Workspace | None:
        tenant = self._resolve_tenant(tenant_id)
        with self._session() as session:
            row = session.execute(
                select(Workspace).where(
                    Workspace.id == workspace_id,
                    Workspace.tenant_id == tenant,
                )
            ).scalar_one_or_none()
            if row is None:
                return None
            for key, value in changes.items():
                if value is not None:
                    setattr(row, key, value)
            session.flush()
            session.refresh(row)
            return row

    def delete_workspace(self, tenant_id: str, workspace_id: str) -> bool:
        tenant = self._resolve_tenant(tenant_id)
        with self._session() as session:
            row = session.execute(
                select(Workspace).where(
                    Workspace.id == workspace_id,
                    Workspace.tenant_id == tenant,
                )
            ).scalar_one_or_none()
            if row is None:
                return False
            session.delete(row)
            return True

    # --- Project --------------------------------------------------------------

    def create_project(
        self,
        tenant_id: str,
        *,
        workspace_id: str,
        name: str,
        description: str | None,
    ) -> Project:
        tenant = self._resolve_tenant(tenant_id)
        now = _utcnow()
        row = Project(
            id=_new_id(),
            tenant_id=tenant,
            workspace_id=workspace_id,
            name=name,
            description=description,
            archived=False,
            created_at=now,
        )
        with self._session() as session:
            session.add(row)
            session.flush()
            session.refresh(row)
            return row

    def get_project(self, tenant_id: str, project_id: str) -> Project | None:
        tenant = self._resolve_tenant(tenant_id)
        with self._session() as session:
            return session.execute(
                select(Project).where(
                    Project.id == project_id,
                    Project.tenant_id == tenant,
                )
            ).scalar_one_or_none()

    def list_projects(self, tenant_id: str, workspace_id: str | None = None) -> list[Project]:
        with self._session() as session:
            stmt = select(Project).where(Project.tenant_id == tenant_id)
            if workspace_id:
                stmt = stmt.where(Project.workspace_id == workspace_id)
            return list(session.execute(stmt).scalars())

    def update_project(
        self, tenant_id: str, project_id: str, **changes: object
    ) -> Project | None:
        tenant = self._resolve_tenant(tenant_id)
        with self._session() as session:
            row = session.execute(
                select(Project).where(
                    Project.id == project_id,
                    Project.tenant_id == tenant,
                )
            ).scalar_one_or_none()
            if row is None:
                return None
            for key, value in changes.items():
                if value is not None:
                    setattr(row, key, value)
            session.flush()
            session.refresh(row)
            return row

    def delete_project(self, tenant_id: str, project_id: str) -> bool:
        tenant = self._resolve_tenant(tenant_id)
        with self._session() as session:
            row = session.execute(
                select(Project).where(
                    Project.id == project_id,
                    Project.tenant_id == tenant,
                )
            ).scalar_one_or_none()
            if row is None:
                return False
            session.delete(row)
            return True

    # --- Website group --------------------------------------------------------

    def create_group(
        self,
        tenant_id: str,
        *,
        project_id: str,
        name: str,
        description: str | None,
    ) -> WebsiteGroup:
        tenant = self._resolve_tenant(tenant_id)
        now = _utcnow()
        row = WebsiteGroup(
            id=_new_id(),
            tenant_id=tenant,
            project_id=project_id,
            name=name,
            description=description,
            created_at=now,
        )
        with self._session() as session:
            session.add(row)
            session.flush()
            session.refresh(row)
            return row

    def list_groups(self, tenant_id: str, project_id: str | None = None) -> list[WebsiteGroup]:
        with self._session() as session:
            stmt = select(WebsiteGroup).where(WebsiteGroup.tenant_id == tenant_id)
            if project_id:
                stmt = stmt.where(WebsiteGroup.project_id == project_id)
            return list(session.execute(stmt).scalars())

    # --- Website --------------------------------------------------------------

    def create_website(
        self,
        tenant_id: str,
        *,
        workspace_id: str,
        project_id: str,
        group_id: str | None,
        name: str,
        url: str,
        display_name: str | None,
        environment: str,
        website_type: str,
    ) -> Website:
        tenant = self._resolve_tenant(tenant_id)
        now = _utcnow()
        row = Website(
            id=_new_id(),
            tenant_id=tenant,
            workspace_id=workspace_id,
            project_id=project_id,
            group_id=group_id,
            name=name,
            url=url,
            display_name=display_name,
            environment=environment,
            website_type=website_type,
            status="CONNECTED",
            onboarding_state="created",
            created_at=now,
            updated_at=now,
        )
        with self._session() as session:
            session.add(row)
            session.flush()
            session.refresh(row)
            return row

    def get_website(self, tenant_id: str, website_id: str) -> Website | None:
        tenant = self._resolve_tenant(tenant_id)
        with self._session() as session:
            return session.execute(
                select(Website).where(
                    Website.id == website_id,
                    Website.tenant_id == tenant,
                )
            ).scalar_one_or_none()

    def list_websites(
        self,
        tenant_id: str,
        *,
        workspace_id: str | None = None,
        project_id: str | None = None,
        group_id: str | None = None,
    ) -> list[Website]:
        with self._session() as session:
            stmt = select(Website).where(Website.tenant_id == tenant_id)
            if workspace_id:
                stmt = stmt.where(Website.workspace_id == workspace_id)
            if project_id:
                stmt = stmt.where(Website.project_id == project_id)
            if group_id:
                stmt = stmt.where(Website.group_id == group_id)
            return list(session.execute(stmt).scalars())

    def list_connected_websites(self, tenant_id: str) -> list[Website]:
        """Return sites with a currently usable, verified CMS connection.

        Feature flags are intentionally not filtered here: the CMO portfolio
        coordinator must see every connected website and report whether AI,
        memory, or automation policy makes it eligible for a particular step.
        """
        tenant = self._resolve_tenant(tenant_id)
        with self._session() as session:
            stmt = (
                select(Website)
                .join(
                    Connection,
                    (Connection.website_id == Website.id)
                    & (Connection.tenant_id == tenant),
                )
                .where(
                    Website.tenant_id == tenant,
                    Connection.is_active.is_(True),
                    Connection.verified_at.is_not(None),
                    Connection.last_error.is_(None),
                )
                .distinct()
            )
            return list(session.execute(stmt).scalars())

    def update_website(
        self, tenant_id: str, website_id: str, **changes: object
    ) -> Website | None:
        tenant = self._resolve_tenant(tenant_id)
        with self._session() as session:
            row = session.execute(
                select(Website).where(
                    Website.id == website_id,
                    Website.tenant_id == tenant,
                )
            ).scalar_one_or_none()
            if row is None:
                return None
            for key, value in changes.items():
                if value is not None:
                    setattr(row, key, value)
            row.updated_at = _utcnow()
            session.flush()
            session.refresh(row)
            return row

    def update_agent_config_section_with_audit(
        self,
        tenant_id: str,
        website_id: str,
        *,
        section: str,
        value: dict,
        expected_section_updated_at: str | None,
        actor_id: str,
        action: str,
        reason: str,
        before_value: str,
        after_value: str,
    ) -> Website | None:
        """Atomically version-check one agent-config section and audit it.

        A row lock serializes PostgreSQL writers. The section timestamp is an
        optimistic check as well, so SQLite/tests and stale callers fail closed
        instead of overwriting newer CMO memory or unrelated agent settings.
        """
        tenant = self._resolve_tenant(tenant_id)
        with self._session() as session:
            row = session.execute(
                select(Website)
                .where(Website.id == website_id, Website.tenant_id == tenant)
                .with_for_update()
            ).scalar_one_or_none()
            if row is None:
                return None
            config = dict(row.agent_config or {})
            current = config.get(section, {})
            current_updated = current.get("updated_at") if isinstance(current, dict) else None
            if current_updated != expected_section_updated_at:
                raise OrchestratorError(
                    "The website CMO memory changed concurrently; reload before retrying."
                )
            config[section] = value
            row.agent_config = config
            row.updated_at = _utcnow()
            session.add(
                OnboardingAudit(
                    id=_new_id(),
                    tenant_id=tenant,
                    website_id=website_id,
                    actor_type="ai_agent",
                    actor_id=actor_id,
                    action=action,
                    reason=reason,
                    before_value=before_value,
                    after_value=after_value,
                    rollback_available=False,
                    approval_required=False,
                    created_at=_utcnow(),
                )
            )
            session.flush()
            session.refresh(row)
            return row

    def delete_website(self, tenant_id: str, website_id: str) -> bool:
        tenant = self._resolve_tenant(tenant_id)
        with self._session() as session:
            row = session.execute(
                select(Website).where(
                    Website.id == website_id,
                    Website.tenant_id == tenant,
                )
            ).scalar_one_or_none()
            if row is None:
                return False
            session.delete(row)
            return True

    # --- Connection -----------------------------------------------------------

    def create_connection(
        self,
        tenant_id: str,
        *,
        website_id: str,
        connection_type: str,
        encrypted_credentials: str | None,
        connection_meta: dict | None,
        capabilities: dict | None,
    ) -> Connection:
        tenant = self._resolve_tenant(tenant_id)
        now = _utcnow()
        row = Connection(
            id=_new_id(),
            tenant_id=tenant,
            website_id=website_id,
            connection_type=connection_type,
            encrypted_credentials=encrypted_credentials,
            connection_meta=connection_meta,
            capabilities=capabilities,
            is_active=True,
            created_at=now,
        )
        with self._session() as session:
            session.add(row)
            session.flush()
            session.refresh(row)
            return row

    def get_connection(self, tenant_id: str, connection_id: str) -> Connection | None:
        tenant = self._resolve_tenant(tenant_id)
        with self._session() as session:
            return session.execute(
                select(Connection).where(
                    Connection.id == connection_id,
                    Connection.tenant_id == tenant,
                )
            ).scalar_one_or_none()

    def list_connections(self, tenant_id: str, website_id: str) -> list[Connection]:
        with self._session() as session:
            return list(
                session.execute(
                    select(Connection).where(
                        Connection.tenant_id == tenant_id,
                        Connection.website_id == website_id,
                    )
                ).scalars()
            )

    def update_connection(
        self, tenant_id: str, connection_id: str, **changes: object
    ) -> Connection | None:
        tenant = self._resolve_tenant(tenant_id)
        with self._session() as session:
            row = session.execute(
                select(Connection).where(
                    Connection.id == connection_id,
                    Connection.tenant_id == tenant,
                )
            ).scalar_one_or_none()
            if row is None:
                return None
            for key, value in changes.items():
                if value is not None:
                    setattr(row, key, value)
            session.flush()
            session.refresh(row)
            return row

    def delete_connection(self, tenant_id: str, connection_id: str) -> bool:
        tenant = self._resolve_tenant(tenant_id)
        with self._session() as session:
            row = session.execute(
                select(Connection).where(
                    Connection.id == connection_id,
                    Connection.tenant_id == tenant,
                )
            ).scalar_one_or_none()
            if row is None:
                return False
            session.delete(row)
            return True

    # --- Integration ----------------------------------------------------------

    def create_integration(
        self,
        tenant_id: str,
        *,
        website_id: str,
        provider: str,
        status: str,
        encrypted_token: str | None = None,
        metadata: dict | None = None,
    ) -> Integration:
        tenant = self._resolve_tenant(tenant_id)
        now = _utcnow()
        row = Integration(
            id=_new_id(),
            tenant_id=tenant,
            website_id=website_id,
            provider=provider,
            status=status,
            encrypted_token=encrypted_token,
            integration_meta=metadata,
            created_at=now,
        )
        with self._session() as session:
            session.add(row)
            session.flush()
            session.refresh(row)
            return row

    def list_integrations(self, tenant_id: str, website_id: str) -> list[Integration]:
        with self._session() as session:
            return list(
                session.execute(
                    select(Integration).where(
                        Integration.tenant_id == tenant_id,
                        Integration.website_id == website_id,
                    )
                ).scalars()
            )

    def update_integration(
        self, tenant_id: str, integration_id: str, **changes: object
    ) -> Integration | None:
        tenant = self._resolve_tenant(tenant_id)
        with self._session() as session:
            row = session.execute(
                select(Integration).where(
                    Integration.id == integration_id,
                    Integration.tenant_id == tenant,
                )
            ).scalar_one_or_none()
            if row is None:
                return None
            for key, value in changes.items():
                if value is not None:
                    setattr(row, key, value)
            session.flush()
            session.refresh(row)
            return row

    # --- Audit ----------------------------------------------------------------

    def record_audit(
        self,
        tenant_id: str,
        *,
        website_id: str | None,
        actor_type: str,
        actor_id: str,
        action: str,
        reason: str | None = None,
        before_value: str | None = None,
        after_value: str | None = None,
        rollback_available: bool = False,
        approval_required: bool = False,
        execution_time_ms: int | None = None,
        tokens_used: int | None = None,
        model: str | None = None,
        cost_usd: float | None = None,
    ) -> OnboardingAudit:
        tenant = self._resolve_tenant(tenant_id)
        row = OnboardingAudit(
            id=_new_id(),
            tenant_id=tenant,
            website_id=website_id,
            actor_type=actor_type,
            actor_id=actor_id,
            action=action,
            reason=reason,
            before_value=before_value,
            after_value=after_value,
            rollback_available=rollback_available,
            approval_required=approval_required,
            execution_time_ms=execution_time_ms,
            tokens_used=tokens_used,
            model=model,
            cost_usd=cost_usd,
            created_at=_utcnow(),
        )
        with self._session() as session:
            session.add(row)
            session.flush()
            session.refresh(row)
            return row

    def list_audit(
        self, tenant_id: str, website_id: str | None = None, limit: int = 100
    ) -> list[OnboardingAudit]:
        with self._session() as session:
            stmt = select(OnboardingAudit).where(
                OnboardingAudit.tenant_id == tenant_id
            )
            if website_id:
                stmt = stmt.where(OnboardingAudit.website_id == website_id)
            stmt = stmt.order_by(OnboardingAudit.created_at.desc()).limit(limit)
            return list(session.execute(stmt).scalars())
