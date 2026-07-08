"""Agency Management Engine models (§4.7)."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

__all__ = [
    "Organization",
    "Client",
    "Team",
    "Role",
    "Workspace",
    "Task",
    "Notification",
    "RoleName",
    "PermissionAction",
    "PermissionScope",
]


class RoleName(str, Enum):
    OWNER = "owner"
    ADMIN = "admin"
    MANAGER = "manager"
    SEO_SPECIALIST = "seo_specialist"
    CONTENT_WRITER = "content_writer"
    CLIENT = "client"
    READ_ONLY = "read_only"


class PermissionAction(str, Enum):
    READ = "read"
    WRITE = "write"
    APPROVE = "approve"
    PUBLISH = "publish"
    ADMIN = "admin"


class PermissionScope(str, Enum):
    ORGANIZATION = "organization"
    CLIENT = "client"
    WORKSPACE = "workspace"


@dataclass(frozen=True)
class Organization:
    """Top-level tenant entity (§4.7, §3.5)."""
    organization_id: str
    name: str
    branding: dict[str, Any] = field(default_factory=dict)  # Logo, colors, client-facing name
    created_at: datetime = field(default_factory=lambda: datetime.now())


@dataclass(frozen=True)
class Client:
    """Client entity (belongs to organization) (§4.7)."""
    client_id: str
    organization_id: str
    name: str
    contact_email: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now())


@dataclass(frozen=True)
class Team:
    """Team within organization (§4.7)."""
    team_id: str
    organization_id: str
    name: str
    members: list[str] = field(default_factory=list)  # User IDs


@dataclass(frozen=True)
class Role:
    """Role with permissions (§4.7). Roles: owner, admin, editor, viewer, client_readonly."""
    role_name: RoleName | str
    permissions: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Workspace:
    """Saved workspace view/context (UX-serving) (§4.7)."""
    workspace_id: str
    organization_id: str
    user_id: str
    name: str
    client_refs: list[str] = field(default_factory=list)
    site_refs: list[str] = field(default_factory=list)
    pinned_dashboards: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Task:
    """Lightweight task referencing engine findings (§4.7)."""
    task_id: str
    organization_id: str
    client_id: str
    title: str
    description: str
    referenced_finding_id: str | None = None  # References any engine's output by ID
    assignee_id: str | None = None
    status: str = "open"  # "open", "in_progress", "completed"
    created_at: datetime = field(default_factory=lambda: datetime.now())


@dataclass(frozen=True)
class Notification:
    """Notification entity with delivery channels (§4.7)."""
    notification_id: str
    organization_id: str
    recipient_id: str
    channel: str  # "in_app", "email", "sms"
    message: str
    status: str = "pending"  # "pending", "sent", "failed"
    created_at: datetime = field(default_factory=lambda: datetime.now())
    sent_at: datetime | None = None
