"""Local SEO Engine interface (§4.3)."""
from __future__ import annotations
import time
from datetime import datetime, timezone
from core.results import Err, Ok, Result
from engines.shared.engine_contract import (
    EngineAnalysisRequest,
    EngineAnalysisResult,
    EngineError,
)
from growth.local_seo.models import LocalSeoReport

__all__ = ["LocalSeoEngine"]


class LocalSeoEngine:
    """
    Sitewide/per-location Local SEO Engine (§4.3).
    
    Analytical Engine protocol.
    REAL: NAP consistency checking.
    Provider-fake: GBP optimization, citation management, directory submissions.
    """

    engine_name = "local_seo"
    engine_version = "1.0.0"

    def supports(self, request_type: str) -> bool:
        return request_type == "site"

    def analyze(
        self, request: EngineAnalysisRequest
    ) -> Result[EngineAnalysisResult, EngineError]:
        """Analyze site for local SEO opportunities. Service does actual work."""
        start = time.perf_counter()
        try:
            # Service layer does actual analysis
            report = LocalSeoReport(
                site_id=request.target.target_id,
                locations=[],
                nap_consistency=None,  # type: ignore - service populates
                local_seo_score={"overall": 0.0, "breakdown": {}},
                computed_at=datetime.now(timezone.utc),
                version=1,
            )
            result = EngineAnalysisResult(
                engine_name=self.engine_name,
                engine_version=self.engine_version,
                target=request.target,
                output=report,
                computed_at=report.computed_at,
            )
        except Exception as exc:
            return Err(EngineError(
                message=f"LocalSeo failed: {exc}",
                engine_name=self.engine_name,
            ))
        duration_ms = int((time.perf_counter() - start) * 1000)
        return Ok(result)
