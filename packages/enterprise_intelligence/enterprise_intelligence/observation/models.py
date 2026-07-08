"""Observation data models — typed events for continuous monitoring (Phase 1).

These models carry observations produced by source adapters.  They are
pure data — no side effects, no tool calls, no governance-gated actions.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

__all__ = [
    "EventSeverity",
    "EventCategory",
    "ObservationEvent",
    "CorrelatedEventGroup",
    "DriftResult",
    "TrendResult",
    "AnomalyResult",
    "KpiAlert",
]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class EventSeverity(str, Enum):
    """Observation event severity."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class EventCategory(str, Enum):
    """Domain category for an observation event."""

    RANKING = "ranking"
    CONTENT = "content"
    TECHNICAL = "technical"
    BACKLINK = "backlink"
    COMPETITOR = "competitor"
    ANALYTICS = "analytics"
    REPUTATION = "reputation"
    LOCAL_SEO = "local_seo"
    COST = "cost"
    PLATFORM_HEALTH = "platform_health"
    SECURITY = "security"


class ObservationEvent(BaseModel):
    """A single typed observation event produced by a source adapter.

    This is the atomic unit of the observation pipeline.  It carries
    structured data about a change noticed in some part of the platform,
    classified and prioritised, but it *never* triggers an action itself.
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id: str
    site_id: str
    category: EventCategory
    severity: EventSeverity = EventSeverity.INFO
    source_engine: str
    source_ref: str
    title: str
    description: str
    data: dict[str, Any] = Field(default_factory=dict)
    confidence: float = 1.0
    business_impact_score: float = 0.0  # 0.0–1.0 normalised
    created_at: datetime = Field(default_factory=_utc_now)
    version: int = 1


class CorrelatedEventGroup(BaseModel):
    """A group of time-correlated observation events across sources."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id: str
    event_ids: list[str] = Field(default_factory=list)
    correlation_type: str
    confidence: float = 0.0
    description: str = ""
    created_at: datetime = Field(default_factory=_utc_now)


# ---------------------------------------------------------------------------
# Statistical detection results
# ---------------------------------------------------------------------------

class DriftResult(BaseModel):
    """Result of a drift-detection check on a metric time-series."""

    metric_name: str
    baseline_mean: float
    current_mean: float
    drift_magnitude: float  # absolute change
    drift_percentage: float
    is_significant: bool
    window_size: int


class TrendResult(BaseModel):
    """Result of a linear trend-detection on a metric time-series."""

    metric_name: str
    slope: float  # positive = upward, negative = downward
    r_squared: float  # goodness-of-fit
    direction: str  # "up", "down", "stable"
    is_significant: bool


class AnomalyResult(BaseModel):
    """Result of anomaly detection on a single observation."""

    metric_name: str
    value: float
    mean: float
    std_dev: float
    z_score: float
    is_anomaly: bool
    method: str = "z_score"  # "z_score" or "iqr"


class KpiAlert(BaseModel):
    """A KPI threshold-breach alert."""

    kpi_name: str
    current_value: float
    threshold: float
    direction: str  # "above" or "below"
    severity: EventSeverity
