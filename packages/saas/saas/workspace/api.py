"""FastAPI Router endpoints for System 1 AI Workspace."""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from saas.workspace.models import Workspace, CanvasNode
from saas.workspace.services import WorkspaceService, CanvasService, CommandPaletteService

__all__ = ["build_workspace_router"]


class NodeCreateRequest(BaseModel):
    canvas_id: str
    node_type: str
    label: str
    x: float
    y: float
    width: float = 120.0
    height: float = 80.0
    metadata_payload: dict[str, Any] = {}


def build_workspace_router(
    ws_service: WorkspaceService,
    canvas_service: CanvasService,
    cmd_service: CommandPaletteService,
) -> APIRouter:
    router = APIRouter(prefix="/v1", tags=["AI Workspace"])

    @router.get("/workspaces", response_model=list[Workspace])
    def get_workspaces(tenant_id: str) -> list[Workspace]:
        # Thin delegator to repo/service
        return ws_service._repo.list_all(tenant_id)

    @router.post("/workspaces/{id}/canvas/nodes", response_model=CanvasNode)
    def create_canvas_node(id: str, req: NodeCreateRequest, tenant_id: str) -> CanvasNode:
        return canvas_service.add_node(
            tenant_id=tenant_id,
            canvas_id=req.canvas_id,
            node_type=req.node_type,
            label=req.label,
            x=req.x,
            y=req.y,
            width=req.width,
            height=req.height,
            metadata_payload=req.metadata_payload,
        )

    @router.delete("/workspaces/{id}/canvas/nodes/{node_id}")
    def delete_canvas_node(id: str, node_id: str, canvas_id: str, tenant_id: str) -> dict[str, bool]:
        success = canvas_service._repo.delete_node(
            tenant_id=tenant_id,
            canvas_id=canvas_id,
            node_id=node_id,
        )
        if not success:
            raise HTTPException(status_code=404, detail="Node not found")
        return {"success": True}

    @router.get("/workspaces/commands")
    def search_commands(query: str = "") -> list[dict[str, Any]]:
        return cmd_service.search_actions(query)

    return router
