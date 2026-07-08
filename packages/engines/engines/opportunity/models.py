"""Opportunity Engine output models (§4.9).

Prioritized work items combining effort, impact, and business context.
Scores are computed deterministically from upstream engine outputs;
``ai_justification`` is the only AI-generated field (narrative, not the score).
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field

__all__ = [
    "EffortLevel",
    "Opportunity",
    "OpportunityReport",
]


class EffortLevel(str, Enum):
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"


class Opportunity(BaseModel):
    """One prioritized work item (§4.9)."""

    id: str
    source_finding_ref: str        # e.g. "technical_seo/{page_id}/{check_name}"
    source_engine: str             # which engine produced the underlying finding
    effort: EffortLevel
    impact_estimate: float         # 0.0-1.0 heuristic, honestly labeled
    revenue_potential: float | None = None  # null unless commercial-intent page
    quick_win: bool = False        # high impact + small effort
    critical: bool = False         # severity-driven, independent of effort/impact
    priority_score: float = 0.0   # deterministic composite (effort * impact)
    #: AI-produced narrative explanation for the prioritization.
    ai_justification: str = ""
    data_completeness: float = 1.0  # propagated from upstream data sources
    computed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class OpportunityReport(BaseModel):
    """Sitewide opportunity prioritization (§4.9)."""

    site_id: str
    tenant_id: str
    version: int = 1
    opportunities: list[Opportunity] = Field(default_factory=list)
    quick_wins: list[str] = Field(default_factory=list)    # opportunity ids
    critical_issues: list[str] = Field(default_factory=list)
    computed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
