"""Opportunity Engine interface (§4.9)."""
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
from engines.opportunity.models import OpportunityReport

__all__ = ["OpportunityEngine"]


class OpportunityEngine:
    """Sitewide Opportunity Engine (§4.9)."""

    engine_name = "opportunity"
    engine_version = "1.0.0"

    def supports(self, target: AnalysisTarget) -> bool:
        return isinstance(target, SiteTarget)

    def analyze(
        self, request: EngineAnalysisRequest
    ) -> Result[EngineAnalysisResult, EngineError]:
        if not isinstance(request.target, SiteTarget):
            return Err(EngineAnalysisError("OpportunityEngine requires a SiteTarget"))
        start = time.perf_counter()
        try:
            from engines.opportunity.services import OpportunityService  # noqa: PLC0415
            service = OpportunityService()
            report: OpportunityReport = service.analyze(
                request.target.site_id,
                site_context=request.site_context,
                options=request.options,
            )
        except Exception as exc:
            return Err(EngineAnalysisError(f"OpportunityEngine failed: {exc}"))
        duration_ms = int((time.perf_counter() - start) * 1000)
        return Ok(EngineAnalysisResult(
            engine_name=self.engine_name,
            engine_version=self.engine_version,
            target=request.target,
            output=report,
            computed_at=datetime.now(timezone.utc),
            duration_ms=duration_ms,
        ))
