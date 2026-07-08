"""Agency Management repositories (section 4.7)."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from core.results import Err, Ok, Result
from growth.agency_management.models import (
    Client,
    Notification,
    Organization,
    Task,
    Team,
    Workspace,
)
from growth.db import (
    ClientRow,
    NotificationRow,
    OrganizationRow,
    TaskRow,
    TeamRow,
    WorkspaceRow,
)
from growth.errors import GrowthStorageError
from intelligence.repositories._session import SessionMixin

__all__ = ["AgencyManagementRepository"]


class AgencyManagementRepository(SessionMixin):
    """Agency Management persistence. CRUD operations, not versioned reports."""

    def __init__(
        self,
        session_source: Session | sessionmaker[Session] | object,
        *,
        tenant_id: str | None = None,
    ) -> None:
        super().__init__(session_source, tenant_id=tenant_id)

    def save_organization(
        self, org: Organization
    ) -> Result[Organization, GrowthStorageError]:
        now = datetime.now(timezone.utc)
        try:
            with self._session() as session:
                row = session.get(OrganizationRow, org.organization_id)
                if row is None:
                    row = OrganizationRow(
                        id=org.organization_id,
                        name=org.name,
                        slug=None,
                        branding_config=org.branding,
                        settings={},
                        created_at=org.created_at,
                        updated_at=now,
                        payload={},
                    )
                    session.add(row)
                else:
                    row.name = org.name
                    row.branding_config = org.branding
                    row.updated_at = now
            return Ok(org)
        except Exception as exc:  # noqa: BLE001
            return Err(GrowthStorageError(f"Failed to save organization: {exc}"))

    def get_organization(
        self, org_id: str
    ) -> Result[Organization | None, GrowthStorageError]:
        try:
            with self._session() as session:
                row = session.get(OrganizationRow, org_id)
                return Ok(self._organization_from_row(row) if row is not None else None)
        except Exception as exc:  # noqa: BLE001
            return Err(GrowthStorageError(f"Failed to get organization: {exc}"))

    def save_client(self, client: Client) -> Result[Client, GrowthStorageError]:
        now = datetime.now(timezone.utc)
        try:
            with self._session() as session:
                row = session.get(ClientRow, client.client_id)
                payload = {"contact_email": client.contact_email}
                if row is None:
                    row = ClientRow(
                        id=client.client_id,
                        organization_id=client.organization_id,
                        name=client.name,
                        slug=None,
                        created_at=client.created_at,
                        updated_at=now,
                        payload=payload,
                    )
                    session.add(row)
                else:
                    row.organization_id = client.organization_id
                    row.name = client.name
                    row.updated_at = now
                    row.payload = payload
            return Ok(client)
        except Exception as exc:  # noqa: BLE001
            return Err(GrowthStorageError(f"Failed to save client: {exc}"))

    def list_clients(self, org_id: str) -> Result[list[Client], GrowthStorageError]:
        try:
            with self._session() as session:
                rows = session.execute(
                    select(ClientRow).where(ClientRow.organization_id == org_id)
                ).scalars().all()
                return Ok([self._client_from_row(row) for row in rows])
        except Exception as exc:  # noqa: BLE001
            return Err(GrowthStorageError(f"Failed to list clients: {exc}"))

    def save_team(self, team: Team) -> Result[Team, GrowthStorageError]:
        try:
            with self._session() as session:
                row = session.get(TeamRow, team.team_id)
                payload = {"members": team.members}
                if row is None:
                    row = TeamRow(
                        id=team.team_id,
                        organization_id=team.organization_id,
                        name=team.name,
                        created_at=datetime.now(timezone.utc),
                        payload=payload,
                    )
                    session.add(row)
                else:
                    row.organization_id = team.organization_id
                    row.name = team.name
                    row.payload = payload
            return Ok(team)
        except Exception as exc:  # noqa: BLE001
            return Err(GrowthStorageError(f"Failed to save team: {exc}"))

    def list_teams(self, org_id: str) -> Result[list[Team], GrowthStorageError]:
        try:
            with self._session() as session:
                rows = session.execute(
                    select(TeamRow).where(TeamRow.organization_id == org_id)
                ).scalars().all()
                return Ok([self._team_from_row(row) for row in rows])
        except Exception as exc:  # noqa: BLE001
            return Err(GrowthStorageError(f"Failed to list teams: {exc}"))

    def save_workspace(
        self, workspace: Workspace
    ) -> Result[Workspace, GrowthStorageError]:
        try:
            with self._session() as session:
                row = session.get(WorkspaceRow, workspace.workspace_id)
                payload = {
                    "user_id": workspace.user_id,
                    "client_refs": workspace.client_refs,
                    "site_refs": workspace.site_refs,
                    "pinned_dashboards": workspace.pinned_dashboards,
                }
                if row is None:
                    row = WorkspaceRow(
                        id=workspace.workspace_id,
                        organization_id=workspace.organization_id,
                        client_id=workspace.client_refs[0]
                        if workspace.client_refs
                        else None,
                        name=workspace.name,
                        created_by=workspace.user_id,
                        created_at=datetime.now(timezone.utc),
                        payload=payload,
                    )
                    session.add(row)
                else:
                    row.organization_id = workspace.organization_id
                    row.client_id = workspace.client_refs[0] if workspace.client_refs else None
                    row.name = workspace.name
                    row.created_by = workspace.user_id
                    row.payload = payload
            return Ok(workspace)
        except Exception as exc:  # noqa: BLE001
            return Err(GrowthStorageError(f"Failed to save workspace: {exc}"))

    def save_task(
        self, task: Task, tenant_id: str | None = None
    ) -> Result[Task, GrowthStorageError]:
        tenant = self._resolve_tenant(tenant_id)
        now = datetime.now(timezone.utc)
        try:
            with self._session() as session:
                payload = {
                    "title": task.title,
                    "description": task.description,
                }
                row = session.get(TaskRow, task.task_id)
                if row is None:
                    row = TaskRow(
                        id=task.task_id,
                        tenant_id=tenant,
                        organization_id=task.organization_id,
                        client_id=task.client_id,
                        site_id=None,
                        assignee_ref=task.assignee_id,
                        status=task.status,
                        priority="medium",
                        reference_entity_type="finding"
                        if task.referenced_finding_id
                        else None,
                        reference_entity_id=task.referenced_finding_id,
                        created_at=task.created_at,
                        updated_at=now,
                        payload=payload,
                    )
                    session.add(row)
                elif row.tenant_id == tenant:
                    row.organization_id = task.organization_id
                    row.client_id = task.client_id
                    row.assignee_ref = task.assignee_id
                    row.status = task.status
                    row.reference_entity_id = task.referenced_finding_id
                    row.updated_at = now
                    row.payload = payload
            return Ok(task)
        except Exception as exc:  # noqa: BLE001
            return Err(GrowthStorageError(f"Failed to save task: {exc}"))

    def update_task_status(
        self, task_id: str, status: str, tenant_id: str | None = None
    ) -> Result[Task | None, GrowthStorageError]:
        tenant = self._resolve_tenant(tenant_id)
        try:
            with self._session() as session:
                row = session.get(TaskRow, task_id)
                if row is None or row.tenant_id != tenant:
                    return Ok(None)
                row.status = status
                row.updated_at = datetime.now(timezone.utc)
                return Ok(self._task_from_row(row))
        except Exception as exc:  # noqa: BLE001
            return Err(GrowthStorageError(f"Failed to update task status: {exc}"))

    def save_notification(
        self, notification: Notification, tenant_id: str | None = None
    ) -> Result[Notification, GrowthStorageError]:
        tenant = self._resolve_tenant(tenant_id)
        try:
            with self._session() as session:
                payload = {
                    "message": notification.message,
                    "status": notification.status,
                    "sent_at": notification.sent_at.isoformat()
                    if notification.sent_at
                    else None,
                }
                row = session.get(NotificationRow, notification.notification_id)
                if row is None:
                    row = NotificationRow(
                        id=notification.notification_id,
                        tenant_id=tenant,
                        organization_id=notification.organization_id,
                        recipient_ref=notification.recipient_id,
                        channel=notification.channel,
                        is_read=0,
                        created_at=notification.created_at,
                        payload=payload,
                    )
                    session.add(row)
                elif row.tenant_id == tenant:
                    row.organization_id = notification.organization_id
                    row.recipient_ref = notification.recipient_id
                    row.channel = notification.channel
                    row.payload = payload
            return Ok(notification)
        except Exception as exc:  # noqa: BLE001
            return Err(GrowthStorageError(f"Failed to save notification: {exc}"))

    def list_notifications(
        self, recipient_id: str, tenant_id: str | None = None
    ) -> Result[list[Notification], GrowthStorageError]:
        tenant = self._resolve_tenant(tenant_id)
        try:
            with self._session() as session:
                rows = session.execute(
                    select(NotificationRow).where(
                        NotificationRow.tenant_id == tenant,
                        NotificationRow.recipient_ref == recipient_id,
                    )
                ).scalars().all()
                return Ok([self._notification_from_row(row) for row in rows])
        except Exception as exc:  # noqa: BLE001
            return Err(GrowthStorageError(f"Failed to list notifications: {exc}"))

    @staticmethod
    def _organization_from_row(row: OrganizationRow) -> Organization:
        return Organization(
            organization_id=row.id,
            name=row.name,
            branding=dict(row.branding_config or {}),
            created_at=row.created_at,
        )

    @staticmethod
    def _client_from_row(row: ClientRow) -> Client:
        return Client(
            client_id=row.id,
            organization_id=row.organization_id,
            name=row.name,
            contact_email=(row.payload or {}).get("contact_email"),
            created_at=row.created_at,
        )

    @staticmethod
    def _team_from_row(row: TeamRow) -> Team:
        return Team(
            team_id=row.id,
            organization_id=row.organization_id,
            name=row.name,
            members=list((row.payload or {}).get("members", [])),
        )

    @staticmethod
    def _task_from_row(row: TaskRow) -> Task:
        payload = row.payload or {}
        return Task(
            task_id=row.id,
            organization_id=row.organization_id or "",
            client_id=row.client_id or "",
            title=payload.get("title", ""),
            description=payload.get("description", ""),
            referenced_finding_id=row.reference_entity_id,
            assignee_id=row.assignee_ref,
            status=row.status,
            created_at=row.created_at,
        )

    @staticmethod
    def _notification_from_row(row: NotificationRow) -> Notification:
        payload = row.payload or {}
        sent_at = payload.get("sent_at")
        return Notification(
            notification_id=row.id,
            organization_id=row.organization_id or "",
            recipient_id=row.recipient_ref,
            channel=row.channel,
            message=payload.get("message", ""),
            status=payload.get("status", "pending"),
            created_at=row.created_at,
            sent_at=datetime.fromisoformat(sent_at) if sent_at else None,
        )
