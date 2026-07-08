"""Scheduler service (M5 Phase 3)."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from brain.scheduler.models import AutomationRule, ExecutionLog, OrchestrationSchedule
from brain.scheduler.repositories import (
    AutomationRuleRepository,
    ExecutionLogRepository,
    ScheduleRepository,
)

__all__ = ["PlatformScheduler"]

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PlatformScheduler:
    """Mock executor of schedules and rules for the M5 blueprint."""

    def __init__(
        self,
        schedule_repo: ScheduleRepository,
        rule_repo: AutomationRuleRepository,
        log_repo: ExecutionLogRepository,
    ) -> None:
        self._schedule_repo = schedule_repo
        self._rule_repo = rule_repo
        self._log_repo = log_repo

    def trigger_schedule(self, tenant_id: str, site_id: str, schedule_id: str) -> str:
        """Trigger an execution of a schedule."""
        logger.info("Triggering schedule %s for %s/%s", schedule_id, tenant_id, site_id)
        
        # Start execution
        log_id = f"exec_{uuid.uuid4().hex[:12]}"
        log = ExecutionLog(
            id=log_id,
            tenant_id=tenant_id,
            site_id=site_id,
            source_id=schedule_id,
            source_type="schedule",
            started_at=_utc_now(),
            status="running",
            logs=["Schedule execution started."],
        )
        self._log_repo.save(log)
        
        # In a real implementation, this would queue a Celery task.
        # For M5, we mock immediate completion.
        log.status = "success"
        log.completed_at = _utc_now()
        log.logs.append("Schedule executed successfully (mock).")
        self._log_repo.save(log)
        
        return log_id

    def evaluate_rules(self, tenant_id: str, site_id: str, event_context: dict) -> None:
        """Evaluate rules against an event context."""
        rules = self._rule_repo.get_all_for_site(tenant_id, site_id, active_only=True)
        
        for rule in rules:
            # Simplistic mock rule evaluation
            # In a real engine, this would parse `rule.condition_expression`
            
            # Pretend we matched
            matched = True
            if matched:
                self._execute_rule(rule, event_context)

    def _execute_rule(self, rule: AutomationRule, context: dict) -> None:
        """Execute an automation rule action."""
        logger.info("Executing rule %s (%s)", rule.id, rule.action_type)
        
        log_id = f"exec_{uuid.uuid4().hex[:12]}"
        log = ExecutionLog(
            id=log_id,
            tenant_id=rule.tenant_id,
            site_id=rule.site_id,
            source_id=rule.id,
            source_type="rule",
            started_at=_utc_now(),
            status="success",
            completed_at=_utc_now(),
            logs=[f"Rule triggered action: {rule.action_type}"],
        )
        self._log_repo.save(log)
        
        rule.execution_count += 1
        self._rule_repo.save(rule)
