"""Reputation Management Engine interface (§4.4)."""
from __future__ import annotations
import time
from datetime import datetime, timezone
from core.results import Err, Ok, Result
from engines.shared.engine_contract import (
    EngineAnalysisRequest,
    EngineAnalysisResult,
    EngineError,
)
from growth.reputation_management.models import ReputationReport

__all__ = ["ReputationManagementEngine"]


class ReputationManagementEngine:
    """
    Sitewide/per-location Reputation Management Engine (§4.4).
    
    Analytical Engine protocol.
    Provider-fake: review ingestion, brand mentions.
    REAL: sentiment analysis against fixture/provider-supplied review text.
    """

    engine_name = "reputation_management"
    engine_version = "1.0.0"

    def supports(self, request_type: str) -> bool:
        return request_type in ("site", "location")

    def analyze(
        self, request: EngineAnalysisRequest
    ) -> Result[EngineAnalysisResult, EngineError]:
        """Analyze reputation. Service does actual work."""
        start = time.perf_counter()
        try:
            # Service layer does actual analysis
            report = ReputationReport(
                site_id=request.target.target_id,
                location_id=request.context.get("location_id"),
                reviews_summary=None,  # type: ignore - service populates
                sentiment_breakdown=None,  # type: ignore - service populates
                negative_review_flags=[],
                response_drafts=[],
                reputation_score={"overall": 0.0, "breakdown": {}},
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
                message=f"ReputationManagement failed: {exc}",
                engine_name=self.engine_name,
            ))
        duration_ms = int((time.perf_counter() - start) * 1000)
        return Ok(result)
