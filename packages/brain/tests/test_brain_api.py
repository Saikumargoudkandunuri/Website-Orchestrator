"""Tests for Brain API endpoints."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from brain.api.routes import build_brain_router
from brain.knowledge_graph.models import KGNode, KGNodeType, WebsiteKnowledgeGraph
from brain.models import SiteSynthesis
from brain.decision.models import PrioritizedDecision
from brain.scheduler.models import OrchestrationSchedule, ScheduleType


def _build_test_app(brain_container: MagicMock) -> FastAPI:
    app = FastAPI()
    app.state.brain = brain_container
    app.include_router(build_brain_router())
    return app


class TestBrainSynthesisAPI:
    """Brain synthesis API endpoints."""

    def test_get_synthesis_not_found(self) -> None:
        container = MagicMock()
        container.seo_brain.get_latest_synthesis.return_value = None
        container.tenant_id = "t1"
        app = _build_test_app(container)
        client = TestClient(app)

        resp = client.get("/brain/sites/site-1/synthesis")
        assert resp.status_code == 404

    def test_get_synthesis_found(self) -> None:
        synthesis = SiteSynthesis(
            id="synth-1",
            site_id="site-1",
            tenant_id="t1",
            engines_with_data=5,
        )
        container = MagicMock()
        container.seo_brain.get_latest_synthesis.return_value = synthesis
        container.tenant_id = "t1"
        app = _build_test_app(container)
        client = TestClient(app)

        resp = client.get("/brain/sites/site-1/synthesis")
        assert resp.status_code == 200
        data = resp.json()
        assert data["site_id"] == "site-1"
        assert data["engines_with_data"] == 5

    def test_trigger_synthesis(self) -> None:
        synthesis = SiteSynthesis(
            id="synth-new",
            site_id="site-1",
            tenant_id="t1",
        )
        container = MagicMock()
        container.seo_brain.get_synthesis.return_value = synthesis
        container.seo_brain.save_synthesis.return_value = synthesis
        container.tenant_id = "t1"
        app = _build_test_app(container)
        client = TestClient(app)

        resp = client.post("/brain/sites/site-1/synthesize")
        assert resp.status_code == 200
        data = resp.json()
        assert data["site_id"] == "site-1"
        container.seo_brain.get_synthesis.assert_called_once_with("t1", "site-1")
        container.seo_brain.save_synthesis.assert_called_once()


class TestBrainKnowledgeGraphAPI:
    """Knowledge Graph API endpoints."""

    def test_get_empty_knowledge_graph(self) -> None:
        empty_graph = WebsiteKnowledgeGraph(
            site_id="site-1",
            tenant_id="t1",
            nodes=[],
            edges=[],
        )
        container = MagicMock()
        container.kg_repo.load_graph.return_value = empty_graph
        container.tenant_id = "t1"
        app = _build_test_app(container)
        client = TestClient(app)

        resp = client.get("/brain/sites/site-1/knowledge-graph")
        assert resp.status_code == 200
        data = resp.json()
        assert data["node_count"] == 0
        assert data["edge_count"] == 0

    def test_get_knowledge_graph_with_nodes(self) -> None:
        graph = WebsiteKnowledgeGraph(
            site_id="site-1",
            tenant_id="t1",
            nodes=[
                KGNode(id="n1", node_type=KGNodeType.PAGE, label="Home", site_id="site-1", tenant_id="t1"),
                KGNode(id="n2", node_type=KGNodeType.ENTITY, label="Python", site_id="site-1", tenant_id="t1"),
            ],
        )
        container = MagicMock()
        container.kg_repo.load_graph.return_value = graph
        container.tenant_id = "t1"
        app = _build_test_app(container)
        client = TestClient(app)

        resp = client.get("/brain/sites/site-1/knowledge-graph")
        assert resp.status_code == 200
        data = resp.json()
        assert data["node_count"] == 2

    def test_get_knowledge_graph_with_type_filter(self) -> None:
        container = MagicMock()
        container.kg_repo.load_graph.return_value = WebsiteKnowledgeGraph(
            site_id="site-1", tenant_id="t1",
        )
        container.tenant_id = "t1"
        app = _build_test_app(container)
        client = TestClient(app)

        resp = client.get("/brain/sites/site-1/knowledge-graph?node_type=page")
        assert resp.status_code == 200
        container.kg_repo.load_graph.assert_called_once_with("t1", "site-1", node_type="page")


class TestBrainDecisionAPI:
    """Decision Engine API endpoints."""

    def test_generate_decisions(self) -> None:
        container = MagicMock()
        container.tenant_id = "t1"
        container.seo_brain.get_latest_synthesis.return_value = MagicMock()
        container.kg_repo.load_graph.return_value = MagicMock()
        container.decision_engine.evaluate_synthesis.return_value = [
            PrioritizedDecision(
                id="dec-1",
                tenant_id="t1",
                site_id="s1",
                title="Title",
                description="Desc",
                source_engine="engine",
                source_ref="ref",
                recommended_action="Do",
            )
        ]
        
        app = _build_test_app(container)
        client = TestClient(app)

        resp = client.post("/brain/sites/site-1/decisions")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["id"] == "dec-1"
        container.decision_engine.evaluate_synthesis.assert_called_once()

    def test_get_decisions(self) -> None:
        container = MagicMock()
        container.tenant_id = "t1"
        container.decision_repo.get_all_for_site.return_value = []
        
        app = _build_test_app(container)
        client = TestClient(app)

        resp = client.get("/brain/sites/site-1/decisions")
        assert resp.status_code == 200
        assert resp.json() == []
        container.decision_repo.get_all_for_site.assert_called_once_with("t1", "site-1")


class TestBrainSchedulerAPI:
    """Scheduler API endpoints."""
    
    def test_get_schedules(self) -> None:
        container = MagicMock()
        container.tenant_id = "t1"
        container.schedule_repo.get_all_for_site.return_value = [
            OrchestrationSchedule(
                id="sched-1",
                tenant_id="t1",
                site_id="s1",
                name="Daily",
                schedule_type=ScheduleType.CRON,
                schedule_expression="0 0 * * *",
            )
        ]
        
        app = _build_test_app(container)
        client = TestClient(app)

        resp = client.get("/brain/sites/site-1/schedules")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["id"] == "sched-1"

    def test_trigger_schedule(self) -> None:
        container = MagicMock()
        container.tenant_id = "t1"
        container.scheduler.trigger_schedule.return_value = "exec-123"
        
        app = _build_test_app(container)
        client = TestClient(app)

        resp = client.post("/brain/sites/site-1/schedules/sched-1/trigger")
        assert resp.status_code == 200
        assert resp.json()["execution_log_id"] == "exec-123"
        container.scheduler.trigger_schedule.assert_called_once_with("t1", "site-1", "sched-1")
