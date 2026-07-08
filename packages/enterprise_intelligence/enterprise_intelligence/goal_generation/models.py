"""Autonomous Goal Models (Phase 3).

Subclasses M6 Goal models to add continuous autonomous tracking parameters
like expiration, ROI estimates, and confidence levels.
"""

from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field

from agentic.goal.models import Goal, GoalContext, StructuredObjective

__all__ = ["AutonomousGoal"]


class AutonomousGoal(Goal):
    """Subclass of M6 Goal adding fields specific to continuous operations.

    Ensures full backward compatibility with M6 planning/runtime engine,
    while carrying expiration, ROI, and safety heuristics.
    """

    expiration_at: datetime | None = None
    estimated_roi: float | None = None
    success_criteria: str | None = None
    confidence: float = 1.0
    risk: float = 0.0
    trigger_type: str = "unknown"
