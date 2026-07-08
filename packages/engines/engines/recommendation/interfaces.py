"""Recommendation Engine interface (§4.10)."""
from __future__ import annotations

import time
from datetime import datetime, timezone

from core.results import Err, Ok, Result
from engines.errors import EngineAnalysisError, EngineError
from engines.shared.engine_contract import (
    AnalysisTarget,
    EngineAnalysisRequest,
    EngineAnalysisResult,
    PageTarget,
    SiteTarget,
)
from engines.recommendation.models import RecommendationReport

__all__ = ["RecommendationEngine"]


class RecommendationEngine:
    """Per-page and sitewide Recommendation Engine (§4.10)."""

    engine_name = "recommendation"
    engine_version = "1.0.0"

    def supports(self, target: AnalysisTarget) -> bool:
        return isinstance(target, (PageTarget, SiteTarget))

    def analyze(
        self, request: EngineAnalysisRequest
    ) -> Result[EngineAnalysisResult, EngineError]:
        if not isinstance(request.target, (PageTarget, SiteTarget)):
            return Err(EngineAnalysisError("RecommendationEngine requires a PageTarget or SiteTarget"))
        start = time.perf_counter()
        try:
            from engines.recommendation.services import RecommendationService  # noqa: PLC0415
            service = RecommendationService()
            if isinstance(request.target, PageTarget):
                report: RecommendationReport = service.analyze(
                    request.target.page_id,
                    request.target.site_id,
                    knowledge_object=request.knowledge_object,
                    site_context=request.site_context,
                    options=request.options,
                )
            else:
                report = service.analyze(
                    None,
                    request.target.site_id,
                    knowledge_object=request.knowledge_object,
                    site_context=request.site_context,
                    options=request.options,
                )
        except Exception as exc:
            return Err(EngineAnalysisError(f"RecommendationEngine failed: {exc}"))
        duration_ms = int((time.perf_counter() - start) * 1000)
        return Ok(EngineAnalysisResult(
            engine_name=self.engine_name,
            engine_version=self.engine_version,
            target=request.target,
            output=report,
            computed_at=datetime.now(timezone.utc),
            duration_ms=duration_ms,
        ))
