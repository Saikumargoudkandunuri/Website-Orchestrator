"""AI Visibility / GEO engine (§1.9 / §2.6 / §5 P6)."""
from __future__ import annotations

from datetime import datetime, timezone

from core.results import Err, Ok, Result
from engines.ai_visibility.models import AiVisibilityReport
from engines.ai_visibility.services import AiVisibilityService
from engines.shared.engine_contract import (
    AnalysisTarget,
    EngineAnalysisRequest,
    EngineAnalysisResult,
    SiteTarget,
)

__all__ = ["AiVisibilityEngine"]

_PLATFORMS = ("chatgpt", "perplexity", "gemini", "google_ai_overview")


class AiVisibilityEngine:
    """Site-level AI visibility / GEO engine (§5 P6)."""

    engine_name = "ai_visibility"
    engine_version = "1.0.0"

    def supports(self, target: AnalysisTarget) -> bool:
        return isinstance(target, SiteTarget)

    def analyze(
        self, request: EngineAnalysisRequest
    ) -> Result[EngineAnalysisResult, Exception]:
        from engines.errors import EngineAnalysisError, EngineError
        if not isinstance(request.target, SiteTarget):
            return Err(EngineAnalysisError("AiVisibilityEngine requires a SiteTarget"))
        try:
            service = AiVisibilityService()
            mentions = request.options.get("ai_mentions", []) if request.options else []
            report = service.analyze(
                request.target.site_id,
                knowledge_object=request.knowledge_object,
                site_context=request.site_context,
                options=request.options,
                mentions=mentions,
            )
        except Exception as exc:
            return Err(EngineAnalysisError(f"AiVisibilityEngine failed: {exc}"))
        return Ok(EngineAnalysisResult(
            engine_name=self.engine_name,
            engine_version=self.engine_version,
            target=request.target,
            output=report,
            computed_at=datetime.now(timezone.utc),
            duration_ms=0,
        ))
