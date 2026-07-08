"""Shared engine contract (§2): every engine implements this protocol.

Defines ``Engine``, ``AnalysisTarget``, ``EngineAnalysisRequest``, and
``EngineAnalysisResult`` — the five-piece typed contract shared identically by
all ten engines so that adding an eleventh engine is a matter of following a
template, not inventing new plumbing.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field

from intelligence.models.ai_invocation import AIInvocation

__all__ = [
    "PageTarget",
    "SiteTarget",
    "CrawlTarget",
    "AnalysisTarget",
    "EngineAnalysisRequest",
    "EngineAnalysisResult",
    "Engine",
]


# ---------------------------------------------------------------------------
# Analysis targets
# ---------------------------------------------------------------------------

class PageTarget(BaseModel):
    """A single page, identified by its stable ``page_id``."""
    kind: str = "page"
    page_id: str
    site_id: str


class SiteTarget(BaseModel):
    """A whole site, for sitewide engines."""
    kind: str = "site"
    site_id: str


class CrawlTarget(BaseModel):
    """A specific crawl run (useful for incremental auditing)."""
    kind: str = "crawl"
    crawl_id: str
    site_id: str


AnalysisTarget = PageTarget | SiteTarget | CrawlTarget


# ---------------------------------------------------------------------------
# Request / result envelope
# ---------------------------------------------------------------------------

class EngineAnalysisRequest(BaseModel):
    """The common input envelope for every engine's ``analyze()`` method (§2)."""

    target: AnalysisTarget
    knowledge_object: Any | None = None   # KnowledgeObject | None — typed as Any to avoid circular imports
    site_context: Any | None = None       # SiteContext | None — built from crawl graph
    options: dict[str, Any] = Field(default_factory=dict)


class EngineAnalysisResult(BaseModel):
    """The common output envelope returned by every engine's ``analyze()`` method."""

    engine_name: str
    engine_version: str
    target: AnalysisTarget
    output: Any                           # Engine-specific typed model (stored as-is; serialized at repo boundary)
    ai_invocations: list[AIInvocation] = Field(default_factory=list)
    computed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    duration_ms: int = 0


# ---------------------------------------------------------------------------
# Engine protocol
# ---------------------------------------------------------------------------

@runtime_checkable
class Engine(Protocol):
    """The single typed contract every engine implements (§2).

    All ten engines are structurally identical from this contract's perspective;
    the only per-engine variation is in what ``output`` contains and which
    ``AnalysisTarget`` subtype ``supports()`` returns ``True`` for.
    """

    engine_name: str
    engine_version: str

    def analyze(
        self, request: EngineAnalysisRequest
    ) -> "Result[EngineAnalysisResult, EngineError]":  # type: ignore[name-defined]  # noqa
        """Run analysis against ``request.target`` and return a typed result.

        Never raises for a handled failure — returns Err(EngineError) instead so
        the orchestrator can continue running sibling engines on partial failure.
        """
        ...

    def supports(self, target: AnalysisTarget) -> bool:
        """Return ``True`` when this engine can analyze ``target``."""
        ...
