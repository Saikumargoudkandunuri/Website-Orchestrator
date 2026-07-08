"""Workflow Intelligence Models (Phase 4).

Subclasses M6 Plan models to support recurrence schedules, state serialization
for checkpointing, and execution metadata.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from pydantic import Field

from agentic.planning.models import Plan

__all__ = ["LongRunningPlan"]


class LongRunningPlan(Plan):
    """Subclass of M6 Plan supporting cron schedules and process checkpoints.

    Inherits the ExecutionGraph DAG structure from M6 and overlays continuous
    re-triggering rules and restart safeguards.
    """

    is_recurring: bool = False
    cron_expression: str | None = None  # standard 5-field cron
    next_run_at: datetime | None = None
    last_run_at: datetime | None = None
    checkpoint_state: dict[str, Any] = Field(default_factory=dict)
