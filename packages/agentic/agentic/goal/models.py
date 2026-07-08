"""Goal Intelligence models for the Agentic Runtime."""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class RiskLevel(str, Enum):
    """Defines the risk level of an autonomous action."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class GoalPriority(str, Enum):
    """Priority of a goal."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class GoalStatus(str, Enum):
    """Current execution status of a goal."""
    DRAFT = "draft"
    PENDING = "pending"
    PLANNING = "planning"
    EXECUTING = "executing"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class GoalContext(BaseModel):
    """Tenant/Organization/Client context for a goal."""
    tenant_id: str
    organization_id: str | None = None
    client_id: str | None = None
    project_id: str | None = None


class GoalConstraints(BaseModel):
    """Constraints placed on the autonomous execution of a goal."""
    requires_human_approval_above_risk: RiskLevel = RiskLevel.MEDIUM
    max_autonomous_steps: int | None = 10
    max_budget_dollars: float | None = None


class StructuredObjective(BaseModel):
    """A typed target metric, magnitude, timeframe, and scope parsed from free-text."""
    target_metric: str
    magnitude: str | float
    timeframe_days: int | None = None
    target_site_id: str | None = None
    target_page_set: list[str] = Field(default_factory=list)


class GoalOutcome(BaseModel):
    """The measurable outcome of a completed goal."""
    success: bool
    measured_impact: dict[str, Any] = Field(default_factory=dict)


class GoalEvaluation(BaseModel):
    """Human or automated evaluation of the goal's results."""
    score: float
    feedback: str


class Goal(BaseModel):
    """
    A goal represents a structured objective for the Agent Runtime to achieve.
    """
    id: str = Field(default_factory=lambda: str(uuid4()))
    raw_objective: str
    structured_objective: StructuredObjective | None = None
    context: GoalContext
    priority: GoalPriority = GoalPriority.NORMAL
    constraints: GoalConstraints = Field(default_factory=GoalConstraints)
    
    outcome: GoalOutcome | None = None
    evaluation: GoalEvaluation | None = None
    
    status: GoalStatus = GoalStatus.DRAFT
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    version: int = 1
