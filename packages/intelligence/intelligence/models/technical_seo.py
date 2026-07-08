"""Technical SEO section of the SEO Knowledge Object (§4.10).

Almost entirely **observed** / deterministically computed (crawlability,
indexability, redirect chain, duplicate title/meta, broken status). AI is not
required here. ``performance_signals`` is nullable — it may not be measured this
milestone.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

__all__ = ["RedirectHop", "PerformanceSignals", "TechnicalSeoSection"]


class RedirectHop(BaseModel):
    url: str
    status_code: int | None = None


class PerformanceSignals(BaseModel):
    ttfb_ms: float | None = None
    page_weight_bytes: int | None = None


class TechnicalSeoSection(BaseModel):
    crawlable: bool = True  # observed
    indexable: bool = True  # observed
    redirect_chain: list[RedirectHop] = Field(default_factory=list)  # observed
    canonical_issues: list[str] = Field(default_factory=list)  # inferred
    duplicate_title_of: list[str] = Field(default_factory=list)  # observed (page_ids)
    duplicate_meta_of: list[str] = Field(default_factory=list)  # observed
    broken: bool = False  # observed (non-2xx)
    performance_signals: PerformanceSignals | None = None  # observed if available
