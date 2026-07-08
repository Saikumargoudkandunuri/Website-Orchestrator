"""Unit tests for System 4 Automation Studio."""

from __future__ import annotations

import pytest
from saas.automation.models import WorkflowDefinition, WorkflowExecution, WorkflowSuspension
from saas.automation.repositories import AutomationRepository
from saas.automation.services import (
    AutomationEngineService,
    EventRouterService,
    SandboxRunnerService,
    NotificationAdapterService,
)


class TestAutomationSystem:
    def test_sandbox_runner_eval(self):
        sandbox = SandboxRunnerService()
        
        # Test 1: Successful script execution modifying output dict
        code_ok = "output = {'score': input.get('score', 0) * 2}"
        res = sandbox.run_script(code_ok, {"score": 5})
        assert res.get("score") == 10

        # Test 2: Accessing restricted builtins/modules fails
        code_bad = "import os\noutput = {'files': os.listdir('.')}"
        res_bad = sandbox.run_script(code_bad, {})
        assert "error" in res_bad

    def test_workflow_state_machine_steps(self, db_session_factory):
        repo = AutomationRepository(db_session_factory, tenant_id="t1")
        sandbox = SandboxRunnerService()
        notifier = NotificationAdapterService()
        engine = AutomationEngineService(repo, sandbox, notifier)

        # Build workflow: Script step -> Approval step
        wf = WorkflowDefinition(
            id="wf-1",
            tenant_id="t1",
            name="Alt text flow",
            trigger_type="event",
            nodes_json={
                "nodes": [
                    {"id": "step-1", "type": "script", "code": "output = {'alt': 'AI text'}"},
                    {"id": "step-2", "type": "approval"},
                ]
            },
            edges_json={}
        )
        repo.save_definition(wf)

        # Trigger run
        exec_run = engine.start_execution("t1", wf, {})
        
        # Script step finishes, approval step pauses
        assert exec_run.status == "paused"
        assert exec_run.current_node_id == "step-2"
        assert len(exec_run.logs_json["steps"]) == 2

        # Check repository persistence and tenant isolation
        persisted = repo.get_execution("t1", exec_run.id)
        assert persisted is not None
        assert persisted.status == "paused"
        
        # Tenant t2 shouldn't see it
        assert repo.get_execution("t2", exec_run.id) is None

    def test_resume_workflow_run(self, db_session_factory):
        repo = AutomationRepository(db_session_factory, tenant_id="t1")
        sandbox = SandboxRunnerService()
        notifier = NotificationAdapterService()
        engine = AutomationEngineService(repo, sandbox, notifier)

        wf = WorkflowDefinition(
            id="wf-2",
            tenant_id="t1",
            name="Resume flow",
            trigger_type="event",
            nodes_json={"nodes": [{"id": "s-1", "type": "approval"}]},
            edges_json={}
        )
        repo.save_definition(wf)

        exec_run = engine.start_execution("t1", wf, {})
        assert exec_run.status == "paused"

        # Resume with approved=True
        from saas.automation.api import ResumeRequest, build_automation_router
        # Call step directly on service to verify continuation
        exec_run.status = "running"
        repo.save_execution(exec_run)
        repo.remove_suspension("t1", exec_run.id)

        # Let step continue (next step doesn't exist, completes)
        engine.step_execution(exec_run, wf, {})
        assert exec_run.status == "completed"

    def test_event_routing_triggers(self, db_session_factory):
        repo = AutomationRepository(db_session_factory, tenant_id="t1")
        sandbox = SandboxRunnerService()
        notifier = NotificationAdapterService()
        engine = AutomationEngineService(repo, sandbox, notifier)
        router = EventRouterService(engine)

        wf = WorkflowDefinition(
            id="wf-3",
            tenant_id="t1",
            name="Triggered flow",
            trigger_type="event",
            nodes_json={"nodes": []},
            edges_json={}
        )
        repo.save_definition(wf)
        router.register_workflow(wf)

        # Route matched event
        triggered = router.route_event("t1", "ranking", {"rank": 12})
        assert triggered == 1
