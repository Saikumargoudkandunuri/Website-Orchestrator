"""Automation repositories (§4.10)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from core.results import Err, Ok, Result
from growth.db import AutomationExecutionLogRow, AutomationRuleRow
from growth.errors import GrowthStorageError
from growth.shared.automation.automation_rule_engine import AutomationExecutionLog, AutomationRule
from intelligence.repositories._session import SessionMixin

__all__ = ["AutomationRepository"]


class AutomationRepository(SessionMixin):
    """Automation rule persistence. CRUD-oriented, not versioned reports."""

    def __init__(
        self,
        session_source: Session | sessionmaker[Session] | object,
        *,
        tenant_id: str | None = None,
    ) -> None:
        super().__init__(session_source, tenant_id=tenant_id)

    def save_rule(
        self,
        rule: AutomationRule,
        org_id: str | None = None,
        site_id: str | None = None,
        tenant_id: str | None = None,
    ) -> Result[AutomationRule, GrowthStorageError]:
        tenant = self._resolve_tenant(tenant_id or rule.tenant_id)
        now = datetime.now(timezone.utc)
        try:
            payload = rule.model_dump(mode="json")
            with self._session() as session:
                row = session.get(AutomationRuleRow, rule.id)
                if row is None:
                    row = AutomationRuleRow(
                        id=rule.id,
                        tenant_id=tenant,
                        organization_id=org_id or rule.organization_id,
                        site_id=site_id or rule.site_id,
                        trigger_event_type=rule.trigger_event_type,
                        enabled=1 if rule.enabled else 0,
                        created_at=rule.created_at,
                        updated_at=now,
                        payload=payload,
                    )
                    session.add(row)
                else:
                    row.organization_id = org_id or rule.organization_id
                    row.site_id = site_id or rule.site_id
                    row.trigger_event_type = rule.trigger_event_type
                    row.enabled = 1 if rule.enabled else 0
                    row.updated_at = now
                    row.payload = payload
            return Ok(rule)
        except Exception as exc:  # noqa: BLE001
            return Err(GrowthStorageError(f"Failed to save rule: {exc}"))

    def get_rules_for_event(
        self,
        event_type: str,
        tenant_id: str | None = None,
    ) -> Result[list[AutomationRule], GrowthStorageError]:
        tenant = self._resolve_tenant(tenant_id)
        try:
            with self._session() as session:
                rows = session.execute(
                    select(AutomationRuleRow).where(
                        AutomationRuleRow.tenant_id == tenant,
                        AutomationRuleRow.trigger_event_type == event_type,
                        AutomationRuleRow.enabled == 1,
                    )
                ).scalars().all()
                return Ok([AutomationRule.model_validate(row.payload) for row in rows])
        except Exception as exc:  # noqa: BLE001
            return Err(GrowthStorageError(f"Failed to get rules: {exc}"))

    def list_rules(
        self,
        site_id: str,
        tenant_id: str | None = None,
    ) -> Result[list[AutomationRule], GrowthStorageError]:
        tenant = self._resolve_tenant(tenant_id)
        try:
            with self._session() as session:
                rows = session.execute(
                    select(AutomationRuleRow).where(
                        AutomationRuleRow.tenant_id == tenant,
                        AutomationRuleRow.site_id == site_id,
                    )
                ).scalars().all()
                return Ok([AutomationRule.model_validate(row.payload) for row in rows])
        except Exception as exc:  # noqa: BLE001
            return Err(GrowthStorageError(f"Failed to list rules: {exc}"))

    def disable_rule(
        self,
        rule_id: str,
        tenant_id: str | None = None,
    ) -> Result[None, GrowthStorageError]:
        tenant = self._resolve_tenant(tenant_id)
        try:
            with self._session() as session:
                row = session.get(AutomationRuleRow, rule_id)
                if row is not None and row.tenant_id == tenant:
                    row.enabled = 0
                    row.updated_at = datetime.now(timezone.utc)
                    payload = dict(row.payload)
                    payload["enabled"] = False
                    row.payload = payload
            return Ok(None)
        except Exception as exc:  # noqa: BLE001
            return Err(GrowthStorageError(f"Failed to disable rule: {exc}"))

    def save_execution_log(
        self,
        log: AutomationExecutionLog,
        org_id: str | None = None,
        site_id: str | None = None,
        tenant_id: str | None = None,
    ) -> Result[None, GrowthStorageError]:
        tenant = self._resolve_tenant(tenant_id or log.tenant_id)
        try:
            with self._session() as session:
                session.add(AutomationExecutionLogRow(
                    id=log.id,
                    tenant_id=tenant,
                    rule_id=log.rule_id,
                    site_id=site_id or log.site_id,
                    result=log.result,
                    executed_at=log.executed_at,
                    payload=log.model_dump(mode="json"),
                ))
            return Ok(None)
        except Exception as exc:  # noqa: BLE001
            return Err(GrowthStorageError(f"Failed to save log: {exc}"))

    def list_execution_logs(
        self,
        site_id: str,
        tenant_id: str | None = None,
    ) -> Result[list[AutomationExecutionLog], GrowthStorageError]:
        tenant = self._resolve_tenant(tenant_id)
        try:
            with self._session() as session:
                rows = session.execute(
                    select(AutomationExecutionLogRow).where(
                        AutomationExecutionLogRow.tenant_id == tenant,
                        AutomationExecutionLogRow.site_id == site_id,
                    ).order_by(AutomationExecutionLogRow.executed_at.desc())
                ).scalars().all()
                return Ok([AutomationExecutionLog.model_validate(row.payload) for row in rows])
        except Exception as exc:  # noqa: BLE001
            return Err(GrowthStorageError(f"Failed to list logs: {exc}"))