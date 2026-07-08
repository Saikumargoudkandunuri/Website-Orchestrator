"""Workspace Services for System 1."""

from __future__ import annotations

import logging
from typing import Any
from uuid import uuid4

from saas.workspace.models import Workspace, Canvas, CanvasNode
from saas.workspace.repositories import WorkspaceRepository, CanvasRepository

__all__ = [
    "WorkspaceService",
    "CanvasService",
    "CommandPaletteService",
    "DashboardBuilderService",
    "RealtimePresenceService",
]

logger = logging.getLogger(__name__)


class WorkspaceService:
    """Service governing workspaces settings and lifecycles."""

    def __init__(self, repo: WorkspaceRepository) -> None:
        self._repo = repo

    def create_workspace(self, tenant_id: str, name: str) -> Workspace:
        ws = Workspace(
            id=str(uuid4()),
            tenant_id=tenant_id,
            name=name,
        )
        self._repo.save(ws)
        return ws


class CanvasService:
    """Service governing layouts and canvas element positions."""

    def __init__(self, repo: CanvasRepository) -> None:
        self._repo = repo

    def create_canvas(self, tenant_id: str, workspace_id: str, name: str) -> Canvas:
        canvas = Canvas(
            id=str(uuid4()),
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            name=name,
        )
        self._repo.save_canvas(canvas)
        return canvas

    def add_node(
        self,
        tenant_id: str,
        canvas_id: str,
        node_type: str,
        label: str,
        x: float,
        y: float,
        width: float = 120.0,
        height: float = 80.0,
        metadata_payload: dict[str, Any] | None = None,
    ) -> CanvasNode:
        node = CanvasNode(
            id=str(uuid4()),
            tenant_id=tenant_id,
            canvas_id=canvas_id,
            node_type=node_type,
            label=label,
            x=x,
            y=y,
            width=width,
            height=height,
            metadata_payload=metadata_payload or {},
        )
        self._repo.save_node(node)
        return node


class CommandPaletteService:
    """Handles universal action searches (shortcuts and queries)."""

    def search_actions(self, query: str) -> list[dict[str, Any]]:
        actions = [
            {"id": "run_crawl", "title": "Run Full Website Crawl", "category": "system"},
            {"id": "generate_alt_text", "title": "Generate AI Alt-Text Suggestions", "category": "ai"},
            {"id": "view_billing", "title": "Manage Subscription & Billing", "category": "admin"},
            {"id": "view_audits", "title": "Inspect Workspace Audit Logs", "category": "admin"},
        ]
        if not query:
            return actions
        return [a for a in actions if query.lower() in a["title"].lower()]


class DashboardBuilderService:
    """Prepares widgets configuration for React-Grid-Layout grids."""

    def get_layout(self, canvas_id: str) -> list[dict[str, Any]]:
        # Hardcoded default layout for widgets
        return [
            {"i": "traffic_chart", "x": 0, "y": 0, "w": 6, "h": 4},
            {"i": "health_gauge", "x": 6, "y": 0, "w": 3, "h": 2},
            {"i": "token_costs", "x": 6, "y": 2, "w": 3, "h": 2},
        ]


class RealtimePresenceService:
    """In-memory presence cache tracker for multiplayer coordinate broadcast."""

    def __init__(self) -> None:
        # Key: workspace_id -> Dict of client_id -> client presence values
        self._presence_map: dict[str, dict[str, Any]] = {}

    def update_presence(
        self, workspace_id: str, client_id: str, user_identity: dict[str, Any], x: float, y: float
    ) -> dict[str, Any]:
        workspace_users = self._presence_map.setdefault(workspace_id, {})
        workspace_users[client_id] = {
            "client_id": client_id,
            "user": user_identity,
            "x": x,
            "y": y,
            "updated_at": datetime.now().isoformat(),
        }
        return workspace_users

    def remove_client(self, workspace_id: str, client_id: str) -> None:
        if workspace_id in self._presence_map:
            self._presence_map[workspace_id].pop(client_id, None)
