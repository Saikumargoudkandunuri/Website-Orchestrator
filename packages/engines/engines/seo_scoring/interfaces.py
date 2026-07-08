"""SEO Scoring Engine interface (§4.8)."""
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
)
from engines.seo_scoring.models import SeoScoreReport

__all__ = ["SeoScoringEngine"]


class SeoScoringEngine:
    """Per-page SEO Scoring Engine (§4.8)."""

    engine_name = "seo_scoring"
    engine_version = "1.0.0"

    def supports(self, target: AnalysisTarget) -> bool:
        return isinstance(target, PageTarget)

    def analyze(
        self, request: EngineAnalysisRequest
    ) -> Result[EngineAnalysisResult, EngineError]:
        if not isinstance(request.target, PageTarget):
            return Err(EngineAnalysisError("SeoScoringEngine requires a PageTarget"))
        start = time.perf_counter()
        try:
            from engines.seo_scoring.services import SeoScoringService  # noqa: PLC0415
            service = SeoScoringService()
            report: SeoScoreReport = service.analyze(
                request.target.page_id,
                request.target.site_id,
                knowledge_object=request.knowledge_object,
                site_context=request.site_context,
                options=request.options,
            )
        except Exception as exc:
            return Err(EngineAnalysisError(f"SeoScoringEngine failed: {exc}"))
        duration_ms = int((time.perf_counter() - start) * 1000)
        return Ok(EngineAnalysisResult(
            engine_name=self.engine_name,
            engine_version=self.engine_version,
            target=request.target,
            output=report,
            computed_at=datetime.now(timezone.utc),
            duration_ms=duration_ms,
        ))
