"""SiteSynthesis — the read-only cross-engine aggregation model (M5 Phase 1).

A ``SiteSynthesis`` is assembled by ``SeoBrain`` from the latest version of
every relevant M3 and M4 engine output for a given site. It performs NO scoring
or inference — pure aggregation so that Phase 2's Decision Engine has one clean
input surface instead of twenty.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

__all__ = [
    "EngineSummary",
    "SiteSynthesis",
]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class EngineSummary(BaseModel):
    """A lightweight summary of one engine's latest output for a site."""

    engine_name: str
    engine_category: str = "m3"  # "m3" or "m4"
    has_data: bool = False
    latest_version: int | None = None
    computed_at: datetime | None = None
    #: The full engine output stored as-is.  The ``SeoBrain`` does not
    #: interpret it — it is carried for downstream consumers (Decision Engine,
    #: Copilot) to read in a typed manner.
    output: Any | None = None
    #: Propagated data_completeness from the underlying engine output.
    data_completeness: float = 1.0


class SiteSynthesis(BaseModel):
    """Read-only aggregation of all engine outputs for a single site.

    This is *not* a new analysis — it is a structured snapshot of what the
    platform currently knows, assembled from existing engine repositories.
    """

    id: str
    site_id: str
    tenant_id: str
    version: int = 1
    created_at: datetime = Field(default_factory=_utc_now)

    # M3 engine outputs (keyed by engine_name)
    m3_engines: dict[str, EngineSummary] = Field(default_factory=dict)

    # M4 Growth engine outputs (keyed by engine_name)
    m4_engines: dict[str, EngineSummary] = Field(default_factory=dict)

    # Aggregate site metrics derived from the individual engine data
    total_pages_analyzed: int = 0
    total_issues_found: int = 0
    total_opportunities: int = 0
    total_recommendations: int = 0
    overall_seo_score: float | None = None

    #: How many of the 20 engines actually had data for this site.
    engines_with_data: int = 0
    total_engines: int = 20
