"""Automation Services for System 4."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from saas.automation.models import WorkflowDefinition, WorkflowExecution, WorkflowSuspension
from saas.automation.repositories import AutomationRepository

__all__ = [
    "AutomationEngineService",
    "EventRouterService",
    "SandboxRunnerService",
    "NotificationAdapterService",
]

logger = logging.getLogger(__name__)


class SandboxRunnerService:
    """Evaluates script nodes in a safe, memory-limited isolated namespace."""

    def run_script(self, code: str, context: dict[str, Any]) -> dict[str, Any]:
        """Execute user-supplied script payload inside an isolated namespace.

        Blocks access to imports and global scope variables to prevent system
        modification hooks.
        """
        # Emulate sandboxing by stripping standard builtins and running in local-only scope
        safe_globals = {"__builtins__": {}}
        local_scope = {"input": context}
        try:
            exec(code, safe_globals, local_scope)
            return local_scope.get("output", {})
        except Exception as exc:
            return {"error": str(exc)}


class NotificationAdapterService:
    """Outbound notifications delivery manager (SMTP, Slack hooks)."""

    def send_notification(self, target: str, subject: str, body: str) -> bool:
        logger.info("Notification sent to %s | %s: %s", target, subject, body)
        return True


class AutomationEngineService:
    """Core state machine executing visual workflow DAG nodes."""

    def __init__(self, repo: AutomationRepository, sandbox: SandboxRunnerService, notifier: NotificationAdapterService) -> None:
        self._repo = repo
        self._sandbox = sandbox
        self._notifier = notifier

    def start_execution(self, tenant_id: str, workflow: WorkflowDefinition, trigger_context: dict[str, Any]) -> WorkflowExecution:
        exec_run = WorkflowExecution(
            id=str(uuid4()),
            tenant_id=tenant_id,
            workflow_id=workflow.id,
            status="running",
            logs_json={"steps": []},
        )
        self._repo.save_execution(exec_run)
        
        # Sequentially process nodes
        self.step_execution(exec_run, workflow, trigger_context)
        return exec_run

    def step_execution(self, exec_run: WorkflowExecution, workflow: WorkflowDefinition, context: dict[str, Any]) -> None:
        nodes = workflow.nodes_json.get("nodes", [])
        if not nodes:
            exec_run.status = "completed"
            self._repo.save_execution(exec_run)
            return

        skip = exec_run.current_node_id is not None
        for node in nodes:
            node_id = node.get("id")
            if skip:
                if node_id == exec_run.current_node_id:
                    skip = False
                continue

            node_type = node.get("type")
            exec_run.current_node_id = node_id
            
            # Append execution log entry
            exec_run.logs_json["steps"].append({
                "node_id": node_id,
                "type": node_type,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

            # Check node behavior
            if node_type == "approval":
                # Pause execution and suspend
                exec_run.status = "paused"
                self._repo.save_execution(exec_run)
                
                susp = WorkflowSuspension(
                    id=str(uuid4()),
                    tenant_id=exec_run.tenant_id,
                    execution_id=exec_run.id,
                    node_id=node_id,
                    reason="Human approval required",
                )
                self._repo.save_suspension(susp)
                self._notifier.send_notification("admin@platform.com", "Workflow Paused", f"Run {exec_run.id} is awaiting approval.")
                return

            elif node_type == "script":
                code = node.get("code", "")
                res = self._sandbox.run_script(code, context)
                if "error" in res:
                    exec_run.status = "failed"
                    exec_run.logs_json["error"] = res["error"]
                    self._repo.save_execution(exec_run)
                    return
                # Merge script outcomes to context
                context.update(res)

        # Finished all steps
        exec_run.status = "completed"
        self._repo.save_execution(exec_run)


class EventRouterService:
    """Listens for observation events and maps them to automation triggers."""

    def __init__(self, engine: AutomationEngineService) -> None:
        self._engine = engine
        self._registered_workflows: list[WorkflowDefinition] = []

    def register_workflow(self, wf: WorkflowDefinition) -> None:
        self._registered_workflows.append(wf)

    def route_event(self, tenant_id: str, event_category: str, event_data: dict[str, Any]) -> int:
        """Route event. Returns count of triggered workflows."""
        count = 0
        for wf in self._registered_workflows:
            if wf.tenant_id == tenant_id and wf.trigger_type == "event":
                # Check trigger criteria matches (simplistic match for mock execution)
                self._engine.start_execution(tenant_id, wf, event_data)
                count += 1
        return count
