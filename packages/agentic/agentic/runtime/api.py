"""FastAPI router for the Agentic Runtime (M6 Build Phase D)."""
from __future__ import annotations

from typing import Any
from fastapi import APIRouter, HTTPException, Request

from agentic.goal.models import RiskLevel
from agentic.tools.selector import ExecutionPolicy
from agentic.runtime.wiring import RuntimeContainer
from growth.auth import GrowthIdentity


def build_runtime_router() -> APIRouter:
    """Build the agentic runtime router."""
    router = APIRouter(prefix="/agentic/runtime", tags=["agentic-runtime"])
    
    def _runtime(request: Request) -> RuntimeContainer:
        container = getattr(request.app.state, "agentic_runtime", None)
        if container is None:
            raise HTTPException(503, "Agentic runtime container is not available.")
        return container

    def _resolve_identity(request: Request) -> GrowthIdentity:
        # Check authorization headers or use a mock editor identity
        auth_header = request.headers.get("Authorization", "")
        # Defaults to a fully permitted test identity
        permissions = ("admin", "read", "write", "approve", "publish")
        roles = ("owner",)
        
        if "viewer" in auth_header.lower():
            permissions = ("read",)
            roles = ("viewer",)
            
        container = _runtime(request)
        return GrowthIdentity(
            tenant_id=container.tenant_id,
            principal_id="request-principal",
            credential_type="api_key",
            roles=roles,
            permissions=permissions,
        )

    @router.post("/start")
    def start_plan(execution_id: str, plan_data: dict[str, Any], request: Request) -> dict[str, Any]:
        container = _runtime(request)
        identity = _resolve_identity(request)
        
        # Read risk parameters from request if provided, otherwise default policy
        policy = ExecutionPolicy(tenant_id=container.tenant_id, allowed_risk_level=RiskLevel.MEDIUM)
        
        try:
            res = container.runtime.start_plan(
                execution_id=execution_id,
                tenant_id=container.tenant_id,
                plan_data=plan_data,
                identity=identity,
                policy=policy,
            )
            return res
        except Exception as e:
            raise HTTPException(400, str(e))


    @router.post("/pause")
    def pause_plan(execution_id: str, request: Request) -> dict[str, Any]:
        container = _runtime(request)
        try:
            return container.runtime.pause_plan(execution_id, container.tenant_id)
        except Exception as e:
            raise HTTPException(400, str(e))

    @router.post("/resume")
    def resume_plan(execution_id: str, request: Request) -> dict[str, Any]:
        container = _runtime(request)
        identity = _resolve_identity(request)
        try:
            return container.runtime.resume_plan(execution_id, container.tenant_id, identity)
        except Exception as e:
            raise HTTPException(400, str(e))

    @router.post("/cancel")
    def cancel_plan(execution_id: str, request: Request) -> dict[str, Any]:
        container = _runtime(request)
        try:
            return container.runtime.cancel_plan(execution_id, container.tenant_id)
        except Exception as e:
            raise HTTPException(400, str(e))

    @router.get("/{execution_id}")
    def get_execution(execution_id: str, request: Request) -> dict[str, Any]:
        container = _runtime(request)
        res = container.execution_repo.get_execution(container.tenant_id, execution_id)
        if not res:
            raise HTTPException(404, f"Execution plan '{execution_id}' not found.")
        return res

    @router.get("/{execution_id}/history")
    def get_history(execution_id: str, request: Request) -> list[dict[str, Any]]:
        container = _runtime(request)
        # Standard history logs can be read from metrics repository
        return container.metrics_repo.get_metrics(container.tenant_id, execution_id)

    @router.get("/{execution_id}/metrics")
    def get_metrics(execution_id: str, request: Request) -> list[dict[str, Any]]:
        container = _runtime(request)
        return container.metrics_repo.get_metrics(container.tenant_id, execution_id)

    @router.get("/{execution_id}/checkpoint")
    def get_checkpoint(execution_id: str, request: Request) -> dict[str, Any]:
        container = _runtime(request)
        checkpoint = container.checkpoint_manager.load_checkpoint(container.tenant_id, execution_id)
        if not checkpoint:
            raise HTTPException(404, f"Checkpoint for execution '{execution_id}' not found.")
        return checkpoint.model_dump(mode="json")

    @router.post("/step")
    def execute_step(execution_id: str, request: Request) -> dict[str, Any]:
        """Trigger one node execution inside the active plan."""
        container = _runtime(request)
        identity = _resolve_identity(request)
        policy = ExecutionPolicy(tenant_id=container.tenant_id, allowed_risk_level=RiskLevel.MEDIUM)
        
        try:
            return container.runtime.execute_next_node(
                execution_id=execution_id,
                tenant_id=container.tenant_id,
                identity=identity,
                policy=policy,
            )
        except Exception as e:
            raise HTTPException(400, str(e))

    return router
