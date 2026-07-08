"""Automation services (§4.10)."""
from __future__ import annotations

from typing import TYPE_CHECKING

from core.results import Err, Ok, Result
from growth.errors import GrowthAutomationError
from growth.shared.automation.automation_rule_engine import (
    ActionDispatcher,
    AutomationExecutionLog,
    AutomationRule,
    AutomationRuleEngine,
)
from growth.shared.automation.event_bus_interface import DomainEvent, EventBus

if TYPE_CHECKING:
    from growth.automation.repositories import AutomationRepository

__all__ = ["AutomationService"]


class AutomationService:
    """Load persisted rules, evaluate incoming events, dispatch actions, and log."""

    def __init__(
        self,
        event_bus: EventBus,
        repository: "AutomationRepository",
        action_dispatcher: ActionDispatcher,
    ) -> None:
        self._event_bus = event_bus
        self._repo = repository
        self._dispatcher = action_dispatcher
        self._event_bus.subscribe_all(self._handle_event)

    def _handle_event(self, event: DomainEvent) -> None:
        rules_result = self._repo.get_rules_for_event(event.event_type, tenant_id=event.tenant_id)
        if rules_result.is_err:
            return

        engine = AutomationRuleEngine()
        for rule in rules_result.unwrap():
            engine.add_rule(rule)
        for log in engine.evaluate(event, self._dispatcher):
            self._repo.save_execution_log(
                log,
                org_id=event.organization_id,
                site_id=event.site_id,
                tenant_id=event.tenant_id,
            )

    def publish_event(self, event: DomainEvent) -> None:
        """Publish an event through the configured bus."""
        self._event_bus.publish(event)

    def create_rule(self, rule: AutomationRule) -> Result[AutomationRule, GrowthAutomationError]:
        saved = self._repo.save_rule(rule, rule.organization_id, rule.site_id, tenant_id=rule.tenant_id)
        if saved.is_err:
            return Err(GrowthAutomationError(str(saved.unwrap_err())))
        return Ok(saved.unwrap())

    def get_rules(self, site_id: str, tenant_id: str | None = None) -> Result[list[AutomationRule], GrowthAutomationError]:
        rules = self._repo.list_rules(site_id, tenant_id=tenant_id)
        if rules.is_err:
            return Err(GrowthAutomationError(str(rules.unwrap_err())))
        return Ok(rules.unwrap())

    def disable_rule(self, rule_id: str, tenant_id: str | None = None) -> Result[None, GrowthAutomationError]:
        disabled = self._repo.disable_rule(rule_id, tenant_id=tenant_id)
        if disabled.is_err:
            return Err(GrowthAutomationError(str(disabled.unwrap_err())))
        return Ok(None)

    def get_execution_logs(
        self,
        site_id: str,
        tenant_id: str | None = None,
    ) -> Result[list[AutomationExecutionLog], GrowthAutomationError]:
        logs = self._repo.list_execution_logs(site_id, tenant_id=tenant_id)
        if logs.is_err:
            return Err(GrowthAutomationError(str(logs.unwrap_err())))
        return Ok(logs.unwrap())