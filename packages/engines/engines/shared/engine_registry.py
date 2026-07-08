"""Engine registry — maps engine names to Engine implementations (§3).

Analogous to Milestone 1's FixGenerator registry pattern: the orchestrator
resolves engines by name from here, not by hardcoding imports throughout the
orchestration logic.  All ten engines self-register in their own ``__init__.py``
via :func:`register_engine`; the registry is lazily populated so importing the
contract module does not force importing all ten engine implementations.
"""

from __future__ import annotations

from typing import Any

from engines.errors import EngineNotFoundError
from engines.shared.engine_contract import AnalysisTarget, Engine

__all__ = ["EngineRegistry", "default_engine_registry"]

_REGISTRY: dict[str, "Engine"] = {}


class EngineRegistry:
    def __init__(self, engines: list["Engine"] | None = None) -> None:
        self._engines: dict[str, "Engine"] = {}
        for engine in (engines or []):
            self._engines[engine.engine_name] = engine

    def register(self, engine: "Engine") -> None:
        self._engines[engine.engine_name] = engine

    def get(self, name: str) -> "Engine":
        e = self._engines.get(name)
        if e is None:
            raise EngineNotFoundError(
                f"No engine registered under {name!r}. "
                f"Available: {sorted(self._engines)}"
            )
        return e

    def all_engines(self) -> list["Engine"]:
        return list(self._engines.values())

    def engines_for(self, target: AnalysisTarget) -> list["Engine"]:
        return [e for e in self._engines.values() if e.supports(target)]

    def names(self) -> list[str]:
        return sorted(self._engines)


def default_engine_registry() -> EngineRegistry:
    """Return an EngineRegistry pre-populated with all ten engines."""
    from engines.technical_seo import TechnicalSeoEngine
    from engines.site_architecture import SiteArchitectureEngine
    from engines.keyword_intelligence import KeywordIntelligenceEngine
    from engines.content_intelligence import ContentIntelligenceEngine
    from engines.competitor_intelligence import CompetitorIntelligenceEngine
    from engines.backlink_intelligence import BacklinkIntelligenceEngine
    from engines.topical_authority import TopicalAuthorityEngine
    from engines.seo_scoring import SeoScoringEngine
    from engines.opportunity import OpportunityEngine
    from engines.recommendation import RecommendationEngine

    return EngineRegistry([
        TechnicalSeoEngine(),
        SiteArchitectureEngine(),
        KeywordIntelligenceEngine(),
        ContentIntelligenceEngine(),
        CompetitorIntelligenceEngine(),
        BacklinkIntelligenceEngine(),
        TopicalAuthorityEngine(),
        SeoScoringEngine(),
        OpportunityEngine(),
        RecommendationEngine(),
    ])
