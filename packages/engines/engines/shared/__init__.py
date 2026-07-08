"""Shared engine infrastructure (contract, registry, SiteContext, providers)."""

from engines.shared.engine_contract import (
    AnalysisTarget,
    CrawlTarget,
    Engine,
    EngineAnalysisRequest,
    EngineAnalysisResult,
    PageTarget,
    SiteTarget,
)
from engines.shared.engine_orchestrator import EngineOrchestrator, OrchestratorResult
from engines.shared.engine_registry import EngineRegistry, default_engine_registry
from engines.shared.site_context import (
    LinkGraphEdge,
    PageSummary,
    SiteContext,
    SiteContextBuilder,
)

__all__ = [
    "Engine",
    "EngineAnalysisRequest",
    "EngineAnalysisResult",
    "AnalysisTarget",
    "PageTarget",
    "SiteTarget",
    "CrawlTarget",
    "EngineRegistry",
    "default_engine_registry",
    "SiteContext",
    "SiteContextBuilder",
    "PageSummary",
    "LinkGraphEdge",
    "EngineOrchestrator",
    "OrchestratorResult",
]
