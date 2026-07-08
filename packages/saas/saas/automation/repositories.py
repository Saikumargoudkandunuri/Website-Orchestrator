"""Automation Repositories for System 4."""

from __future__ import annotations

from typing import Any
from sqlalchemy import select, delete

from intelligence.repositories._session import SessionMixin
from saas.automation.models import (
    WorkflowDefinitionRow,
    WorkflowExecutionRow,
    WorkflowSuspensionRow,
    WorkflowDefinition,
    WorkflowExecution,
    WorkflowSuspension,
)

__all__ = ["AutomationRepository"]


class AutomationRepository(SessionMixin):
    """SaaS Automation Repository managing definitions, executions, and suspensions."""

    def save_definition(self, wf: WorkflowDefinition) -> None:
        tenant = self._resolve_tenant(wf.tenant_id)
        with self._session() as session:
            existing = session.get(WorkflowDefinitionRow, wf.id)
            if existing:
                existing.name = wf.name
                existing.nodes_json = wf.nodes_json
                existing.edges_json = wf.edges_json
            else:
                session.add(WorkflowDefinitionRow(
                    id=wf.id,
                    tenant_id=tenant,
                    name=wf.name,
                    trigger_type=wf.trigger_type,
                    nodes_json=wf.nodes_json,
                    edges_json=wf.edges_json,
                ))
            session.commit()

    def get_definition(self, tenant_id: str, wf_id: str) -> WorkflowDefinition | None:
        tenant = self._resolve_tenant(tenant_id)
        with self._session() as session:
            row = session.get(WorkflowDefinitionRow, wf_id)
            if row and row.tenant_id == tenant:
                return WorkflowDefinition(
                    id=row.id,
                    tenant_id=row.tenant_id,
                    name=row.name,
                    trigger_type=row.trigger_type,
                    nodes_json=row.nodes_json,
                    edges_json=row.edges_json,
                )
            return None

    def save_execution(self, exec_run: WorkflowExecution) -> None:
        tenant = self._resolve_tenant(exec_run.tenant_id)
        with self._session() as session:
            existing = session.get(WorkflowExecutionRow, exec_run.id)
            if existing:
                existing.status = exec_run.status
                existing.current_node_id = exec_run.current_node_id
                existing.logs_json = exec_run.logs_json
            else:
                session.add(WorkflowExecutionRow(
                    id=exec_run.id,
                    tenant_id=tenant,
                    workflow_id=exec_run.workflow_id,
                    status=exec_run.status,
                    current_node_id=exec_run.current_node_id,
                    logs_json=exec_run.logs_json,
                    created_at=exec_run.created_at,
                ))
            session.commit()

    def get_execution(self, tenant_id: str, exec_id: str) -> WorkflowExecution | None:
        tenant = self._resolve_tenant(tenant_id)
        with self._session() as session:
            row = session.get(WorkflowExecutionRow, exec_id)
            if row and row.tenant_id == tenant:
                return WorkflowExecution(
                    id=row.id,
                    tenant_id=row.tenant_id,
                    workflow_id=row.workflow_id,
                    status=row.status,
                    current_node_id=row.current_node_id,
                    logs_json=row.logs_json,
                    created_at=row.created_at,
                )
            return None

    def save_suspension(self, susp: WorkflowSuspension) -> None:
        tenant = self._resolve_tenant(susp.tenant_id)
        with self._session() as session:
            session.add(WorkflowSuspensionRow(
                id=susp.id,
                tenant_id=tenant,
                execution_id=susp.execution_id,
                node_id=susp.node_id,
                reason=susp.reason,
                created_at=susp.created_at,
            ))
            session.commit()

    def remove_suspension(self, tenant_id: str, exec_id: str) -> None:
        tenant = self._resolve_tenant(tenant_id)
        with self._session() as session:
            session.execute(
                delete(WorkflowSuspensionRow).where(
                    WorkflowSuspensionRow.tenant_id == tenant,
                    WorkflowSuspensionRow.execution_id == exec_id,
                )
            )
            session.commit()
