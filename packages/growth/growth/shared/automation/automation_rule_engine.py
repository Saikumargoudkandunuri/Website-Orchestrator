"""Generic typed AutomationRule evaluator (§4.10, §9).

The rule engine evaluates AutomationConditions against DomainEvent payloads
and dispatches AutomationActions. Every example automation from the spec brief
is expressible as a generic AutomationRule instance with ZERO hardcoded
special-case logic:

- "when crawl finishes → generate report"
- "when issue is critical → notify owner"
- "when ranking drops → create task"
- "when AI finds opportunity → recommend content"
- "when content published → re-crawl"
- "when traffic decreases → trigger AI analysis"

This model is designed to be visual-builder-ready without requiring backend
changes when a drag-and-drop UI is added later.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from growth.shared.automation.event_bus_interface import DomainEvent

__all__ = [
    "AutomationCondition",
    "ConditionOperator",
    # Action types
    "GenerateReportAction",
    "NotifyAction",
    "CreateTaskAction",
    "RecommendContentAction",
    "TriggerRecrawlAction",
    "TriggerAnalysisAction",
    "AutomationAction",
    # Rule + execution log
    "AutomationRule",
    "AutomationExecutionLog",
    "AutomationRuleEngine",
]


class ConditionOperator(str):
    """Supported condition operators."""
    EQ = "eq"
    NEQ = "neq"
    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"
    CONTAINS = "contains"
    EXISTS = "exists"


class AutomationCondition(BaseModel):
    """A typed predicate over the event payload (§4.10).

    Structured, serializable, enumerable — visual-builder-ready.
    """

    field: str    # dot-notation path into event payload, e.g. "severity", "position"
    operator: str = ConditionOperator.EQ  # eq | neq | gt | gte | lt | lte | contains | exists
    value: Any = None  # the value to compare against (not used for "exists")

    def evaluate(self, event: DomainEvent) -> bool:
        """Evaluate this condition against a DomainEvent. Returns True if matched."""
        payload = event.payload
        # Resolve the field value using dot notation
        field_value = self._resolve_field(payload, self.field)

        if self.operator == ConditionOperator.EXISTS:
            return field_value is not None
        if field_value is None:
            return False

        try:
            if self.operator == ConditionOperator.EQ:
                return str(field_value) == str(self.value)
            elif self.operator == ConditionOperator.NEQ:
                return str(field_value) != str(self.value)
            elif self.operator == ConditionOperator.GT:
                return float(field_value) > float(self.value)
            elif self.operator == ConditionOperator.GTE:
                return float(field_value) >= float(self.value)
            elif self.operator == ConditionOperator.LT:
                return float(field_value) < float(self.value)
            elif self.operator == ConditionOperator.LTE:
                return float(field_value) <= float(self.value)
            elif self.operator == ConditionOperator.CONTAINS:
                return str(self.value).lower() in str(field_value).lower()
            else:
                return False
        except (TypeError, ValueError):
            return False

    @staticmethod
    def _resolve_field(payload: dict[str, Any], field_path: str) -> Any:
        """Resolve a dot-notation field path from a payload dict."""
        parts = field_path.split(".")
        current: Any = payload
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None
        return current


# --- Action types (§4.10) ---

class GenerateReportAction(BaseModel):
    """Trigger Reporting Engine to generate a report."""

    action_type: str = "generate_report"
    report_type: str  # "executive", "seo", "technical", etc.
    format: str = "json"


class NotifyAction(BaseModel):
    """Send a notification via a delivery channel."""

    action_type: str = "notify"
    channel: str  # "in_app" | "email" | "sms"
    recipient_ref: str  # organization owner ref, user id, etc.
    message_template: str  # may include {{event.payload.field}} placeholders


class CreateTaskAction(BaseModel):
    """Create a task assigned to a user."""

    action_type: str = "create_task"
    task_template: str  # task title template with placeholders
    assignee_ref: str | None = None
    priority: str = "medium"


class RecommendContentAction(BaseModel):
    """Trigger Content Generation Engine to create content."""

    action_type: str = "recommend_content"
    generation_type: str  # "blog_post", "landing_page", etc.
    context_from_event: list[str] = Field(
        default_factory=list,
        description="Fields to pull from event payload into generation context.",
    )


class TriggerRecrawlAction(BaseModel):
    """Trigger a site recrawl."""

    action_type: str = "trigger_recrawl"
    max_pages: int | None = None


class TriggerAnalysisAction(BaseModel):
    """Trigger a specific engine's analysis."""

    action_type: str = "trigger_analysis"
    engine_name: str


# Discriminated union of all action types
AutomationAction = (
    GenerateReportAction
    | NotifyAction
    | CreateTaskAction
    | RecommendContentAction
    | TriggerRecrawlAction
    | TriggerAnalysisAction
)


# --- AutomationRule ---

class AutomationRule(BaseModel):
    """A generic, typed automation rule (§4.10).

    Structured, serializable, enumerable — visual-builder-ready.
    Every example automation from the spec brief is expressible as one
    AutomationRule instance with ZERO hardcoded special-case logic.
    """

    id: str
    name: str
    trigger_event_type: str  # matches DomainEvent.event_type
    condition: AutomationCondition | None = None  # None = always fire
    action: dict[str, Any]  # serialized AutomationAction (discriminated by action_type)
    enabled: bool = True
    organization_id: str | None = None
    site_id: str | None = None
    tenant_id: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def matches(self, event: DomainEvent) -> bool:
        """Return True if this rule should fire for ``event``."""
        if not self.enabled:
            return False
        if event.event_type != self.trigger_event_type:
            return False
        if self.condition is not None:
            return self.condition.evaluate(event)
        return True

    def get_action(self) -> AutomationAction:
        """Deserialize and return the typed action."""
        action_type = self.action.get("action_type", "")
        _ACTION_MAP = {
            "generate_report": GenerateReportAction,
            "notify": NotifyAction,
            "create_task": CreateTaskAction,
            "recommend_content": RecommendContentAction,
            "trigger_recrawl": TriggerRecrawlAction,
            "trigger_analysis": TriggerAnalysisAction,
        }
        cls = _ACTION_MAP.get(action_type)
        if cls is None:
            raise ValueError(f"Unknown action_type: {action_type!r}")
        return cls(**self.action)


# --- Execution log ---

class AutomationExecutionLog(BaseModel):
    """An audit record for every automation rule firing (§4.10).

    Every automation firing is logged — satisfying the project-wide
    auditability principle.
    """

    id: str
    rule_id: str
    event_ref: str  # DomainEvent identifier (event_type + occurred_at + site_id)
    action_taken: dict[str, Any]  # serialized action
    result: str  # "success" | "failed" | "skipped"
    error_message: str | None = None
    executed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    tenant_id: str = ""
    site_id: str | None = None


# --- Rule Engine ---

class AutomationRuleEngine:
    """Evaluates AutomationRules against DomainEvents and dispatches actions.

    Uses ZERO hardcoded if/else — all behavior is expressed through generic
    AutomationRule instances.
    """

    def __init__(self) -> None:
        self._rules: list[AutomationRule] = []
        self._logs: list[AutomationExecutionLog] = []

    def add_rule(self, rule: AutomationRule) -> None:
        self._rules.append(rule)

    def remove_rule(self, rule_id: str) -> bool:
        before = len(self._rules)
        self._rules = [r for r in self._rules if r.id != rule_id]
        return len(self._rules) < before

    def rules_for_event(self, event_type: str) -> list[AutomationRule]:
        return [r for r in self._rules if r.trigger_event_type == event_type and r.enabled]

    def evaluate(
        self,
        event: DomainEvent,
        action_dispatcher: "ActionDispatcher | None" = None,
    ) -> list[AutomationExecutionLog]:
        """Evaluate all rules against ``event``, dispatch matching actions, return logs."""
        import uuid

        logs: list[AutomationExecutionLog] = []
        for rule in self._rules:
            if not rule.matches(event):
                continue
            event_ref = f"{event.event_type}:{event.site_id}:{event.occurred_at.isoformat()}"
            try:
                action = rule.get_action()
                if action_dispatcher is not None:
                    action_dispatcher.dispatch(action, event, rule)
                log = AutomationExecutionLog(
                    id=uuid.uuid4().hex,
                    rule_id=rule.id,
                    event_ref=event_ref,
                    action_taken=rule.action,
                    result="success",
                    executed_at=datetime.now(timezone.utc),
                    tenant_id=rule.tenant_id,
                    site_id=rule.site_id,
                )
            except Exception as exc:
                log = AutomationExecutionLog(
                    id=uuid.uuid4().hex,
                    rule_id=rule.id,
                    event_ref=event_ref,
                    action_taken=rule.action,
                    result="failed",
                    error_message=str(exc),
                    executed_at=datetime.now(timezone.utc),
                    tenant_id=rule.tenant_id,
                    site_id=rule.site_id,
                )
            self._logs.append(log)
            logs.append(log)
        return logs

    def get_logs(self) -> list[AutomationExecutionLog]:
        return list(self._logs)


class ActionDispatcher:
    """Dispatches typed AutomationActions. Override in tests or production.

    Production implementations connect to real services (job queue, notification
    service, etc.). Test implementations record dispatched actions.
    """

    def dispatch(
        self,
        action: AutomationAction,
        event: DomainEvent,
        rule: AutomationRule,
    ) -> None:
        """Dispatch a typed action. Override in subclasses."""
        pass  # default no-op


class RecordingActionDispatcher(ActionDispatcher):
    """Test double — records all dispatched actions for assertion."""

    def __init__(self) -> None:
        self.dispatched: list[tuple[AutomationAction, DomainEvent, AutomationRule]] = []

    def dispatch(
        self,
        action: AutomationAction,
        event: DomainEvent,
        rule: AutomationRule,
    ) -> None:
        self.dispatched.append((action, event, rule))
