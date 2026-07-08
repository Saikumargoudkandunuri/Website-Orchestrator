"""Topical Authority Engine interface (§4.7)."""
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
from engines.topical_authority.models import TopicalAuthorityReport

__all__ = ["TopicalAuthorityEngine"]


class TopicalAuthorityEngine:
    """Sitewide Topical Authority Engine (§4.7)."""

    engine_name = "topical_authority"
    engine_version = "1.0.0"

    def supports(self, target: AnalysisTarget) -> bool:
        return isinstance(target, SiteTarget)

    def analyze(
        self, request: EngineAnalysisRequest
    ) -> Result[EngineAnalysisResult, EngineError]:
        if not isinstance(request.target, SiteTarget):
            return Err(EngineAnalysisError("TopicalAuthorityEngine requires a SiteTarget"))
        start = time.perf_counter()
        try:
            from engines.topical_authority.services import TopicalAuthorityService  # noqa: PLC0415
            service = TopicalAuthorityService()
            report: TopicalAuthorityReport = service.analyze(
                request.target.site_id,
                site_context=request.site_context,
                options=request.options,
            )
        except Exception as exc:
            return Err(EngineAnalysisError(f"TopicalAuthorityEngine failed: {exc}"))
        duration_ms = int((time.perf_counter() - start) * 1000)
        return Ok(EngineAnalysisResult(
            engine_name=self.engine_name,
            engine_version=self.engine_version,
            target=request.target,
            output=report,
            computed_at=datetime.now(timezone.utc),
            duration_ms=duration_ms,
        ))
