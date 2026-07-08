"""Brain API routes (M5 Phase 1).

Endpoints:
- ``GET  /brain/sites/{site_id}/synthesis`` — latest ``SiteSynthesis``
- ``POST /brain/sites/{site_id}/synthesize`` — trigger synthesis
- ``GET  /brain/sites/{site_id}/knowledge-graph`` — query the KG
- ``POST /brain/sites/{site_id}/decisions`` — generate decisions
- ``GET  /brain/sites/{site_id}/decisions`` — list decisions
- ``GET  /brain/sites/{site_id}/decisions/{decision_id}/outcome`` — get outcome
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from brain.models import SiteSynthesis
from brain.decision.models import PrioritizedDecision, HistoricalOutcome
from brain.scheduler.models import OrchestrationSchedule, AutomationRule, ExecutionLog
from brain.wiring import BrainContainer

__all__ = ["build_brain_router"]


def build_brain_router() -> APIRouter:
    """Build the Brain API router.

    The ``BrainContainer`` is expected on ``request.app.state.brain``.
    """
    router = APIRouter(prefix="/brain", tags=["brain"])

    def _brain(request: Request) -> Any:
        brain = getattr(request.app.state, "brain", None)
        if brain is None:
            raise HTTPException(503, "Brain service is not available.")
        return brain

    @router.get("/sites/{site_id}/synthesis")
    def get_synthesis(site_id: str, request: Request) -> dict[str, Any]:
        """Return the latest persisted SiteSynthesis for a site."""
        container = _brain(request)
        latest = container.seo_brain.get_latest_synthesis(
            container.tenant_id, site_id
        )
        if latest is None:
            raise HTTPException(404, f"No synthesis found for site {site_id}.")
        return latest.model_dump(mode="json")

    @router.post("/sites/{site_id}/synthesize")
    def trigger_synthesis(site_id: str, request: Request) -> dict[str, Any]:
        """Compute and persist a new SiteSynthesis for a site."""
        container = _brain(request)
        synthesis = container.seo_brain.get_synthesis(
            container.tenant_id, site_id
        )
        saved = container.seo_brain.save_synthesis(container.tenant_id, synthesis)
        return saved.model_dump(mode="json")

    @router.get("/sites/{site_id}/knowledge-graph")
    def get_knowledge_graph(
        site_id: str,
        request: Request,
        node_type: str | None = None,
    ) -> dict[str, Any]:
        """Return the Knowledge Graph for a site, optionally filtered by node type."""
        container = _brain(request)
        graph = container.kg_repo.load_graph(
            container.tenant_id,
            site_id,
            node_type=node_type,
        )
        return {
            "site_id": graph.site_id,
            "node_count": len(graph.nodes),
            "edge_count": len(graph.edges),
            "nodes": [n.model_dump(mode="json") for n in graph.nodes],
            "edges": [e.model_dump(mode="json") for e in graph.edges],
        }

    @router.post("/sites/{site_id}/decisions", response_model=list[PrioritizedDecision])
    def generate_decisions(site_id: str, request: Request) -> list[PrioritizedDecision]:
        """Generate prioritized decisions from the latest site synthesis."""
        container: BrainContainer = request.app.state.brain
        tenant_id = container.tenant_id

        synthesis = container.seo_brain.get_latest_synthesis(tenant_id, site_id)
        if not synthesis:
            raise HTTPException(status_code=404, detail="No synthesis found for site")

        graph = container.kg_repo.load_graph(tenant_id, site_id)
        if not graph:
            raise HTTPException(status_code=404, detail="No knowledge graph found for site")

        return container.decision_engine.evaluate_synthesis(synthesis, graph)

    @router.get("/sites/{site_id}/decisions", response_model=list[PrioritizedDecision])
    def get_decisions(site_id: str, request: Request) -> list[PrioritizedDecision]:
        """Retrieve all decisions for a site."""
        container: BrainContainer = request.app.state.brain
        return container.decision_repo.get_all_for_site(container.tenant_id, site_id)

    @router.get("/sites/{site_id}/decisions/{decision_id}/outcome", response_model=HistoricalOutcome)
    def get_decision_outcome(site_id: str, decision_id: str, request: Request) -> HistoricalOutcome:
        """Retrieve the historical outcome for a decision."""
        container: BrainContainer = request.app.state.brain
        outcome = container.historical_repo.get_by_decision(container.tenant_id, decision_id)
        if not outcome:
            raise HTTPException(status_code=404, detail="Outcome not found")
        return outcome

    @router.get("/sites/{site_id}/schedules", response_model=list[OrchestrationSchedule])
    def get_schedules(site_id: str, request: Request) -> list[OrchestrationSchedule]:
        """Retrieve all orchestration schedules for a site."""
        container: BrainContainer = request.app.state.brain
        return container.schedule_repo.get_all_for_site(container.tenant_id, site_id)

    @router.post("/sites/{site_id}/schedules/{schedule_id}/trigger", response_model=dict[str, str])
    def trigger_schedule(site_id: str, schedule_id: str, request: Request) -> dict[str, str]:
        """Manually trigger a schedule."""
        container: BrainContainer = request.app.state.brain
        log_id = container.scheduler.trigger_schedule(container.tenant_id, site_id, schedule_id)
        return {"execution_log_id": log_id}

    @router.get("/sites/{site_id}/automation-rules", response_model=list[AutomationRule])
    def get_automation_rules(site_id: str, request: Request) -> list[AutomationRule]:
        """Retrieve all automation rules for a site."""
        container: BrainContainer = request.app.state.brain
        return container.rule_repo.get_all_for_site(container.tenant_id, site_id)

    @router.get("/sites/{site_id}/execution-logs", response_model=list[ExecutionLog])
    def get_execution_logs(site_id: str, request: Request) -> list[ExecutionLog]:
        """Retrieve execution logs for a site."""
        container: BrainContainer = request.app.state.brain
        return container.log_repo.get_recent(container.tenant_id, site_id)

    return router
