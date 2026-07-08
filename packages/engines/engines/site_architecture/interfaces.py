"""Site Architecture Engine interface (§4.2)."""
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
from engines.site_architecture.models import SiteArchitectureReport

__all__ = ["SiteArchitectureEngine"]


class SiteArchitectureEngine:
    """Sitewide Site Architecture Engine (§4.2)."""

    engine_name = "site_architecture"
    engine_version = "1.0.0"

    def supports(self, target: AnalysisTarget) -> bool:
        return isinstance(target, SiteTarget)

    def analyze(
        self, request: EngineAnalysisRequest
    ) -> Result[EngineAnalysisResult, EngineError]:
        if not isinstance(request.target, SiteTarget):
            return Err(EngineAnalysisError("SiteArchitectureEngine requires a SiteTarget"))
        start = time.perf_counter()
        try:
            from engines.site_architecture.services import SiteArchitectureService  # noqa: PLC0415
            service = SiteArchitectureService()
            report: SiteArchitectureReport = service.analyze(
                request.target.site_id,
                site_context=request.site_context,
                options=request.options,
            )
        except Exception as exc:
            return Err(EngineAnalysisError(f"SiteArchitectureEngine failed: {exc}"))
        duration_ms = int((time.perf_counter() - start) * 1000)
        return Ok(EngineAnalysisResult(
            engine_name=self.engine_name,
            engine_version=self.engine_version,
            target=request.target,
            output=report,
            computed_at=datetime.now(timezone.utc),
            duration_ms=duration_ms,
        ))
