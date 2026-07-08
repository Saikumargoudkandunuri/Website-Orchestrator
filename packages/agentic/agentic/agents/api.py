"""FastAPI router for agent missions and blackboard collaboration (M6 Build Phase F)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from agentic.agents.types import JsonObject
from agentic.agents.wiring import AgentContainer
from agentic.goal.models import RiskLevel
from agentic.tools.selector import ExecutionPolicy
from growth.auth import GrowthIdentity


def build_agent_router() -> APIRouter:
    """Build the multi-agent API router."""
    router = APIRouter(prefix="/agentic/missions", tags=["agentic-missions"])

    def _agents(request: Request) -> AgentContainer:
        container = getattr(request.app.state, "agentic_agents", None)
        if container is None:
            raise HTTPException(503, "Agentic container is not available.")
        return container

    def _resolve_identity(request: Request) -> GrowthIdentity:
        container = _agents(request)
        return GrowthIdentity(
            tenant_id=container.tenant_id,
            principal_id="mission-supervisor",
            credential_type="api_key",
            roles=("owner",),
            permissions=("admin", "read", "write", "approve", "publish"),
        )

    @router.post("")
    def start_mission(goal_id: str, objective: str, request: Request) -> JsonObject:
        container = _agents(request)
        identity = _resolve_identity(request)
        policy = ExecutionPolicy(tenant_id=container.tenant_id, allowed_risk_level=RiskLevel.MEDIUM)
        try:
            result = container.supervisor.execute_mission(
                tenant_id=container.tenant_id,
                goal_id=goal_id,
                objective=objective,
                identity=identity,
                policy=policy,
            )
            container.mission_monitor.log_mission_start(container.tenant_id, str(result["mission_id"]), objective)
            return result
        except Exception as exc:
            raise HTTPException(400, str(exc)) from exc

    @router.get("/{mission_id}")
    def get_mission(mission_id: str, request: Request) -> JsonObject:
        container = _agents(request)
        result = container.mission_manager.get_mission(container.tenant_id, mission_id)
        if not result:
            raise HTTPException(404, f"Mission '{mission_id}' not found.")
        return result.model_dump(mode="json")

    @router.post("/{mission_id}/pause")
    def pause_mission(mission_id: str, request: Request) -> JsonObject:
        container = _agents(request)
        try:
            container.mission_manager.transition_state(container.tenant_id, mission_id, "waiting", reason="human_pause")
            execution_id = f"exec_{mission_id}"
            container.supervisor.runtime.pause_plan(execution_id, container.tenant_id)
            return {"mission_id": mission_id, "state": "waiting"}
        except Exception as exc:
            raise HTTPException(400, str(exc)) from exc

    @router.post("/{mission_id}/resume")
    def resume_mission(mission_id: str, request: Request) -> JsonObject:
        container = _agents(request)
        identity = _resolve_identity(request)
        try:
            container.mission_manager.transition_state(container.tenant_id, mission_id, "executing", reason="human_resume")
            execution_id = f"exec_{mission_id}"
            container.supervisor.runtime.resume_plan(execution_id, container.tenant_id, identity)
            return {"mission_id": mission_id, "state": "executing"}
        except Exception as exc:
            raise HTTPException(400, str(exc)) from exc

    @router.post("/{mission_id}/cancel")
    def cancel_mission(mission_id: str, request: Request) -> JsonObject:
        container = _agents(request)
        try:
            container.mission_manager.transition_state(container.tenant_id, mission_id, "cancelled", reason="human_cancel")
            execution_id = f"exec_{mission_id}"
            container.supervisor.runtime.cancel_plan(execution_id, container.tenant_id)
            return {"mission_id": mission_id, "state": "cancelled"}
        except Exception as exc:
            raise HTTPException(400, str(exc)) from exc

    @router.get("/{mission_id}/agents")
    def list_mission_agents(mission_id: str, request: Request) -> list[JsonObject]:
        container = _agents(request)
        if not container.mission_manager.get_mission(container.tenant_id, mission_id):
            raise HTTPException(404, f"Mission '{mission_id}' not found.")
        return [meta.model_dump(mode="json") for meta in container.agent_registry.list_agents()]

    @router.get("/{mission_id}/blackboard")
    def get_blackboard(mission_id: str, request: Request) -> list[JsonObject]:
        container = _agents(request)
        return container.blackboard.list_entries(container.tenant_id, mission_id)

    @router.get("/{mission_id}/messages")
    def get_messages(mission_id: str, request: Request) -> list[JsonObject]:
        container = _agents(request)
        return container.message_repo.get_messages(container.tenant_id, mission_id)

    @router.get("/{mission_id}/metrics")
    def get_metrics(mission_id: str, request: Request) -> list[JsonObject]:
        container = _agents(request)
        execution_id = f"exec_{mission_id}"
        mission_metrics = container.mission_metrics_repo.get_metrics(container.tenant_id, mission_id)
        runtime_metrics = container.supervisor.runtime.metrics_repo.get_metrics(container.tenant_id, execution_id)
        return mission_metrics + runtime_metrics

    return router
