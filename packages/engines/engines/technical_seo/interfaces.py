"""Technical SEO Engine interface (§4.1)."""
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
from engines.technical_seo.models import TechnicalSeoAudit

__all__ = ["TechnicalSeoEngine"]


class TechnicalSeoEngine:
    """Per-page Technical SEO Engine (§4.1)."""

    engine_name = "technical_seo"
    engine_version = "1.0.0"

    def supports(self, target: AnalysisTarget) -> bool:
        return isinstance(target, PageTarget)

    def analyze(
        self, request: EngineAnalysisRequest
    ) -> Result[EngineAnalysisResult, EngineError]:
        if not isinstance(request.target, PageTarget):
            return Err(EngineAnalysisError("TechnicalSeoEngine requires a PageTarget"))
        start = time.perf_counter()
        try:
            from engines.technical_seo.services import TechnicalSeoService  # noqa: PLC0415
            service = TechnicalSeoService()
            audit: TechnicalSeoAudit = service.analyze(
                request.target.page_id,
                request.target.site_id,
                knowledge_object=request.knowledge_object,
                site_context=request.site_context,
                options=request.options,
            )
        except Exception as exc:
            return Err(EngineAnalysisError(f"TechnicalSeoEngine failed: {exc}"))
        duration_ms = int((time.perf_counter() - start) * 1000)
        return Ok(EngineAnalysisResult(
            engine_name=self.engine_name,
            engine_version=self.engine_version,
            target=request.target,
            output=audit,
            computed_at=datetime.now(timezone.utc),
            duration_ms=duration_ms,
        ))
