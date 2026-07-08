"""Scheduler & Automation Models (M5 Phase 3).

Models the when (OrchestrationSchedule) and the what/if (AutomationRule),
and tracks execution history (ExecutionLog).
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

__all__ = [
    "ScheduleType",
    "OrchestrationSchedule",
    "AutomationRule",
    "ExecutionLog",
]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ScheduleType(str, Enum):
    CRON = "cron"
    INTERVAL = "interval"
    ONCE = "once"


class OrchestrationSchedule(BaseModel):
    """When a specific engine or sequence should run."""
    
    id: str
    tenant_id: str
    site_id: str
    
    name: str
    description: str | None = None
    
    schedule_type: ScheduleType
    schedule_expression: str  # CRON expression or interval string
    
    # Target engines/tasks to execute
    target_tasks: list[str] = Field(default_factory=list)
    
    is_active: bool = True
    last_run_at: datetime | None = None
    next_run_at: datetime | None = None
    
    created_at: datetime = Field(default_factory=_utc_now)


class AutomationRule(BaseModel):
    """When condition X occurs, trigger action Y."""
    
    id: str
    tenant_id: str
    site_id: str
    
    name: str
    
    # Simple rule engine representation
    condition_expression: str  # e.g., "decision.roi > 0.8 AND decision.risk < 0.2"
    action_type: str           # e.g., "auto_approve", "notify_slack"
    action_payload: dict[str, Any] = Field(default_factory=dict)
    
    is_active: bool = True
    execution_count: int = 0
    
    created_at: datetime = Field(default_factory=_utc_now)


class ExecutionLog(BaseModel):
    """History of an orchestrated run or automation rule execution."""
    
    id: str
    tenant_id: str
    site_id: str
    
    source_id: str  # ID of the Schedule or Rule
    source_type: str  # 'schedule' or 'rule'
    
    started_at: datetime
    completed_at: datetime | None = None
    
    status: str  # 'running', 'success', 'failed'
    
    logs: list[str] = Field(default_factory=list)
    error_message: str | None = None
