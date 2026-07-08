"""FastAPI Router endpoints for System 4 Automation Studio."""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from saas.automation.models import WorkflowDefinition, WorkflowExecution
from saas.automation.services import AutomationEngineService

__all__ = ["build_automation_router"]


class WorkflowCreateRequest(BaseModel):
    name: str
    trigger_type: str
    nodes_json: dict[str, Any]
    edges_json: dict[str, Any]


class ResumeRequest(BaseModel):
    approved: bool
    context_updates: dict[str, Any] = {}


def build_automation_router(
    engine: AutomationEngineService,
) -> APIRouter:
    router = APIRouter(prefix="/v1/automation", tags=["Automation Studio"])

    @router.post("/workflows", response_model=WorkflowDefinition)
    def create_workflow(req: WorkflowCreateRequest, tenant_id: str) -> WorkflowDefinition:
        from uuid import uuid4
        wf = WorkflowDefinition(
            id=str(uuid4()),
            tenant_id=tenant_id,
            name=req.name,
            trigger_type=req.trigger_type,
            nodes_json=req.nodes_json,
            edges_json=req.edges_json,
        )
        engine._repo.save_definition(wf)
        return wf

    @router.get("/workflows/{id}", response_model=WorkflowDefinition)
    def get_workflow(id: str, tenant_id: str) -> WorkflowDefinition:
        wf = engine._repo.get_definition(tenant_id, id)
        if not wf:
            raise HTTPException(status_code=404, detail="Workflow not found")
        return wf

    @router.post("/executions/{id}/resume", response_model=WorkflowExecution)
    def resume_execution(id: str, req: ResumeRequest, tenant_id: str) -> WorkflowExecution:
        exec_run = engine._repo.get_execution(tenant_id, id)
        if not exec_run:
            raise HTTPException(status_code=404, detail="Execution trace not found")
        
        if exec_run.status != "paused":
            raise HTTPException(status_code=400, detail="Workflow run is not in suspended state")

        # Delete suspension record
        engine._repo.remove_suspension(tenant_id, id)

        if not req.approved:
            exec_run.status = "failed"
            exec_run.logs_json["steps"].append({
                "node_id": exec_run.current_node_id,
                "type": "approval_rejected",
                "timestamp": "now",
            })
            engine._repo.save_execution(exec_run)
            return exec_run

        # Otherwise resume sequence
        wf = engine._repo.get_definition(tenant_id, exec_run.workflow_id)
        if not wf:
            raise HTTPException(status_code=404, detail="Workflow definition missing")

        exec_run.status = "running"
        engine._repo.save_execution(exec_run)

        # Continue steps
        engine.step_execution(exec_run, wf, req.context_updates)
        return exec_run

    @router.get("/executions/{id}/trace", response_model=WorkflowExecution)
    def get_execution_trace(id: str, tenant_id: str) -> WorkflowExecution:
        exec_run = engine._repo.get_execution(tenant_id, id)
        if not exec_run:
            raise HTTPException(status_code=404, detail="Trace not found")
        return exec_run

    return router
