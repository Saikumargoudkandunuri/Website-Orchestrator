"""Unit tests for System 1 AI Workspace."""

from __future__ import annotations

import pytest
from saas.workspace.models import Workspace, Canvas, CanvasNode
from saas.workspace.repositories import WorkspaceRepository, CanvasRepository
from saas.workspace.services import WorkspaceService, CanvasService, CommandPaletteService


class TestWorkspaceSystem:
    def test_create_and_retrieve_workspace(self, db_session_factory):
        repo = WorkspaceRepository(db_session_factory, tenant_id="t1")
        service = WorkspaceService(repo)
        
        ws = service.create_workspace("t1", "Growth Dashboard")
        assert ws.name == "Growth Dashboard"
        assert ws.tenant_id == "t1"
        
        retrieved = repo.get("t1", ws.id)
        assert retrieved is not None
        assert retrieved.name == "Growth Dashboard"

    def test_tenant_isolation(self, db_session_factory):
        repo_t1 = WorkspaceRepository(db_session_factory, tenant_id="t1")
        service_t1 = WorkspaceService(repo_t1)
        
        repo_t2 = WorkspaceRepository(db_session_factory, tenant_id="t2")
        service_t2 = WorkspaceService(repo_t2)

        ws_t1 = service_t1.create_workspace("t1", "T1 Workspace")
        ws_t2 = service_t2.create_workspace("t2", "T2 Workspace")

        # Cross tenant retrieval should fail/return None
        assert repo_t1.get("t1", ws_t2.id) is None
        assert repo_t2.get("t2", ws_t1.id) is None

        # Listing only shows tenant workspaces
        list_t1 = repo_t1.list_all("t1")
        assert len(list_t1) == 1
        assert list_t1[0].name == "T1 Workspace"

    def test_canvas_nodes_management(self, db_session_factory):
        repo = CanvasRepository(db_session_factory, tenant_id="t1")
        service = CanvasService(repo)

        canvas = service.create_canvas("t1", "ws-123", "Main Strategy Canvas")
        node1 = service.add_node("t1", canvas.id, "goal_card", "Recover organic traffic", 10.0, 20.0)
        node2 = service.add_node("t1", canvas.id, "chart", "Keyword positions", 150.0, 20.0)

        nodes = repo.list_nodes("t1", canvas.id)
        assert len(nodes) == 2
        assert nodes[0].canvas_id == canvas.id

        # Delete node
        deleted = repo.delete_node("t1", canvas.id, node1.id)
        assert deleted is True
        assert len(repo.list_nodes("t1", canvas.id)) == 1

    def test_command_palette_search(self):
        service = CommandPaletteService()
        res_all = service.search_actions("")
        assert len(res_all) == 4
        
        res_crawl = service.search_actions("Crawl")
        assert len(res_crawl) == 1
        assert res_crawl[0]["id"] == "run_crawl"
