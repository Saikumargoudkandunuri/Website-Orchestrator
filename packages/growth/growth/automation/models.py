"""Automation Engine models (§4.10)."""
from __future__ import annotations
# Note: Core models (AutomationRule, DomainEvent, AutomationCondition, AutomationAction)
# are already defined in shared/automation/automation_rule_engine.py
# This module re-exports them for convenience

from growth.shared.automation.event_bus_interface import DomainEvent
from growth.shared.automation.automation_rule_engine import (
    AutomationRule,
    AutomationCondition,
    AutomationAction,
    AutomationExecutionLog,
)

__all__ = [
    "DomainEvent",
    "AutomationRule",
    "AutomationCondition",
    "AutomationAction",
    "AutomationExecutionLog",
]
