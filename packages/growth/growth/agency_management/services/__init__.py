"""Agency Management services (§4.7)."""
from __future__ import annotations
from typing import TYPE_CHECKING
from core.results import Ok, Result
from growth.agency_management.models import (
    Organization,
    Client,
    Team,
    Workspace,
    Task,
    Notification,
)
from growth.errors import GrowthStorageError

if TYPE_CHECKING:
    from growth.agency_management.repositories import AgencyManagementRepository

__all__ = ["AgencyManagementService"]


class AgencyManagementService:
    """
    Agency Management business logic (§4.7).
    
    CRUD-oriented, NOT analyze/generate shaped.
    Manages: Organizations, Clients, Teams, Roles, Workspaces, Tasks, Notifications.
    """
    
    def __init__(self, repository: "AgencyManagementRepository"):
        self._repo = repository
    
    # Organization CRUD
    def create_organization(self, org: Organization) -> Result[Organization, GrowthStorageError]:
        return self._repo.save_organization(org)
    
    def get_organization(self, org_id: str) -> Result[Organization | None, GrowthStorageError]:
        return self._repo.get_organization(org_id)
    
    # Client CRUD
    def create_client(self, client: Client) -> Result[Client, GrowthStorageError]:
        return self._repo.save_client(client)
    
    def list_clients(self, org_id: str) -> Result[list[Client], GrowthStorageError]:
        return self._repo.list_clients(org_id)
    
    # Team CRUD
    def create_team(self, team: Team) -> Result[Team, GrowthStorageError]:
        return self._repo.save_team(team)

    def list_teams(self, org_id: str) -> Result[list[Team], GrowthStorageError]:
        return self._repo.list_teams(org_id)
    
    # Workspace CRUD
    def save_workspace(self, workspace: Workspace) -> Result[Workspace, GrowthStorageError]:
        return self._repo.save_workspace(workspace)
    
    # Task management
    def create_task(self, task: Task) -> Result[Task, GrowthStorageError]:
        return self._repo.save_task(task)
    
    def update_task_status(self, task_id: str, status: str) -> Result[Task | None, GrowthStorageError]:
        return self._repo.update_task_status(task_id, status)
    
    # Notification delivery
    def send_notification(self, notification: Notification) -> Result[Notification, GrowthStorageError]:
        """Send notification via specified channel."""
        # In-app delivery (real)
        if notification.channel == "in_app":
            return self._repo.save_notification(notification)
        
        # Email/SMS delivery (interface with fakes, real integration out of scope)
        # Would delegate to email/SMS service here
        
        return self._repo.save_notification(notification)

    def list_notifications(self, recipient_id: str) -> Result[list[Notification], GrowthStorageError]:
        return self._repo.list_notifications(recipient_id)
