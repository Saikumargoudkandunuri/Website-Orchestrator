"""Backlink Intelligence Engine interface (§4.6)."""
from __future__ import annotations

import time
from datetime import datetime, timezone

from core.results import Err, Ok, Result
from engines.errors import EngineAnalysisError, EngineError
from engines.shared.engine_contract import (
    AnalysisTarget,
    EngineAnalysisRequest,
    EngineAnalysisResult,
    SiteTarget,
)
from engines.backlink_intelligence.models import BacklinkIntelligenceReport

__all__ = ["BacklinkIntelligenceEngine"]


class BacklinkIntelligenceEngine:
    """Sitewide Backlink Intelligence Engine (§4.6)."""

    engine_name = "backlink_intelligence"
    engine_version = "1.0.0"

    def supports(self, target: AnalysisTarget) -> bool:
        return isinstance(target, SiteTarget)

    def analyze(
        self, request: EngineAnalysisRequest
    ) -> Result[EngineAnalysisResult, EngineError]:
        if not isinstance(request.target, SiteTarget):
            return Err(EngineAnalysisError("BacklinkIntelligenceEngine requires a SiteTarget"))
        start = time.perf_counter()
        try:
            from engines.backlink_intelligence.services import BacklinkIntelligenceService  # noqa: PLC0415
            service = BacklinkIntelligenceService()
            report: BacklinkIntelligenceReport = service.analyze(
                request.target.site_id,
                site_context=request.site_context,
                options=request.options,
            )
        except Exception as exc:
            return Err(EngineAnalysisError(f"BacklinkIntelligenceEngine failed: {exc}"))
        duration_ms = int((time.perf_counter() - start) * 1000)
        return Ok(EngineAnalysisResult(
            engine_name=self.engine_name,
            engine_version=self.engine_version,
            target=request.target,
            output=report,
            computed_at=datetime.now(timezone.utc),
            duration_ms=duration_ms,
        ))
