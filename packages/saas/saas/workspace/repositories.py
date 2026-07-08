"""Workspace Repositories for System 1."""

from __future__ import annotations

from typing import Any
from sqlalchemy import select, delete

from intelligence.repositories._session import SessionMixin
from saas.workspace.models import (
    WorkspaceRow,
    CanvasRow,
    CanvasNodeRow,
    WorkspaceAnnotationRow,
    Workspace,
    Canvas,
    CanvasNode,
    WorkspaceAnnotation,
)

__all__ = ["WorkspaceRepository", "CanvasRepository"]


class WorkspaceRepository(SessionMixin):
    """Tenant-scoped repository for managing Workspaces."""

    def save(self, workspace: Workspace) -> None:
        tenant = self._resolve_tenant(workspace.tenant_id)
        with self._session() as session:
            existing = session.get(WorkspaceRow, workspace.id)
            if existing:
                existing.name = workspace.name
            else:
                session.add(WorkspaceRow(
                    id=workspace.id,
                    tenant_id=tenant,
                    name=workspace.name,
                    created_at=workspace.created_at,
                ))
            session.commit()

    def get(self, tenant_id: str, workspace_id: str) -> Workspace | None:
        tenant = self._resolve_tenant(tenant_id)
        with self._session() as session:
            row = session.get(WorkspaceRow, workspace_id)
            if row and row.tenant_id == tenant:
                return Workspace(
                    id=row.id,
                    tenant_id=row.tenant_id,
                    name=row.name,
                    created_at=row.created_at,
                )
            return None

    def list_all(self, tenant_id: str) -> list[Workspace]:
        tenant = self._resolve_tenant(tenant_id)
        with self._session() as session:
            rows = session.execute(
                select(WorkspaceRow).where(WorkspaceRow.tenant_id == tenant)
            ).scalars().all()
            return [
                Workspace(
                    id=r.id,
                    tenant_id=r.tenant_id,
                    name=r.name,
                    created_at=r.created_at,
                )
                for r in rows
            ]


class CanvasRepository(SessionMixin):
    """Tenant-scoped repository for Canvases and CanvasNodes."""

    def save_canvas(self, canvas: Canvas) -> None:
        tenant = self._resolve_tenant(canvas.tenant_id)
        with self._session() as session:
            existing = session.get(CanvasRow, canvas.id)
            if existing:
                existing.name = canvas.name
            else:
                session.add(CanvasRow(
                    id=canvas.id,
                    tenant_id=tenant,
                    workspace_id=canvas.workspace_id,
                    name=canvas.name,
                    created_at=canvas.created_at,
                ))
            session.commit()

    def get_canvas(self, tenant_id: str, canvas_id: str) -> Canvas | None:
        tenant = self._resolve_tenant(tenant_id)
        with self._session() as session:
            row = session.get(CanvasRow, canvas_id)
            if row and row.tenant_id == tenant:
                return Canvas(
                    id=row.id,
                    tenant_id=row.tenant_id,
                    workspace_id=row.workspace_id,
                    name=row.name,
                    created_at=row.created_at,
                )
            return None

    def save_node(self, node: CanvasNode) -> None:
        tenant = self._resolve_tenant(node.tenant_id)
        with self._session() as session:
            existing = session.get(CanvasNodeRow, node.id)
            if existing:
                existing.label = node.label
                existing.x = node.x
                existing.y = node.y
                existing.width = node.width
                existing.height = node.height
                existing.metadata_payload = node.metadata_payload
            else:
                session.add(CanvasNodeRow(
                    id=node.id,
                    tenant_id=tenant,
                    canvas_id=node.canvas_id,
                    node_type=node.node_type,
                    label=node.label,
                    x=node.x,
                    y=node.y,
                    width=node.width,
                    height=node.height,
                    metadata_payload=node.metadata_payload,
                ))
            session.commit()

    def delete_node(self, tenant_id: str, canvas_id: str, node_id: str) -> bool:
        tenant = self._resolve_tenant(tenant_id)
        with self._session() as session:
            row = session.get(CanvasNodeRow, node_id)
            if row and row.tenant_id == tenant and row.canvas_id == canvas_id:
                session.delete(row)
                session.commit()
                return True
            return False

    def list_nodes(self, tenant_id: str, canvas_id: str) -> list[CanvasNode]:
        tenant = self._resolve_tenant(tenant_id)
        with self._session() as session:
            rows = session.execute(
                select(CanvasNodeRow).where(
                    CanvasNodeRow.tenant_id == tenant,
                    CanvasNodeRow.canvas_id == canvas_id,
                )
            ).scalars().all()
            return [
                CanvasNode(
                    id=r.id,
                    tenant_id=r.tenant_id,
                    canvas_id=r.canvas_id,
                    node_type=r.node_type,
                    label=r.label,
                    x=r.x,
                    y=r.y,
                    width=r.width,
                    height=r.height,
                    metadata_payload=r.metadata_payload,
                )
                for r in rows
            ]
