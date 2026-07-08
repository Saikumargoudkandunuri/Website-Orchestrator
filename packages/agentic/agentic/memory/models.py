"""Data models for the cognitive memory layer (M6 Build Phase C)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from agentic.goal.models import Goal


class ExperienceEpisode(BaseModel):
    """An execution/event experience stored in Episodic Memory."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id: str
    site_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    actor: str
    goal_id: str | None = None
    execution_graph_id: str | None = None
    actions: list[dict[str, Any]] = Field(default_factory=list)
    results: list[dict[str, Any]] = Field(default_factory=list)
    duration_hours: float = 0.0
    cost_dollars: float = 0.0
    success: bool = True
    errors: list[str] = Field(default_factory=list)
    approval_path: list[str] = Field(default_factory=list)
    correlation_id: str = Field(default_factory=lambda: str(uuid4()))


class SemanticFact(BaseModel):
    """A business fact or preference stored in Semantic Memory."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id: str
    key: str
    value: Any
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    reference_id: str | None = None  # e.g., references an external KnowledgeObject


class WorkflowTemplate(BaseModel):
    """A reusable procedural workflow template."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id: str
    name: str
    ordered_steps: list[dict[str, Any]] = Field(default_factory=list)
    required_approvals: list[str] = Field(default_factory=list)
    estimated_cost: float = 0.0
    estimated_duration: float = 0.0
    rollback_strategy: str = ""
    required_tools: list[str] = Field(default_factory=list)


class ReflectionLesson(BaseModel):
    """A lesson learned derived from continuous observations."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id: str
    lesson: str
    confidence: float = 0.0  # 0.0 to 1.0
    evidence: list[str] = Field(default_factory=list)
    related_executions: list[str] = Field(default_factory=list)
    related_goals: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class GoalMemoryRecord(BaseModel):
    """Goal state tracking information."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id: str
    goal: Goal
    status: str = "pending"
    current_progress: float = 0.0  # e.g., 0.0 to 1.0 (100%)
    blocked_reasons: list[str] = Field(default_factory=list)
    deadline: datetime | None = None
    priority: str = "normal"
    related_execution_graphs: list[str] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MemoryIndex(BaseModel):
    """An index linking memory across cognitive domains."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id: str
    entity_type: str  # e.g., "episode", "lesson", "knowledge_object"
    entity_id: str
    tags: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
