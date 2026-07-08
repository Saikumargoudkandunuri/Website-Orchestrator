"""Outreach & Link Building Engine interface (§4.9)."""
from __future__ import annotations
from datetime import datetime, timezone
from core.results import Ok, Result
from engines.shared.engine_contract import EngineAnalysisRequest, EngineAnalysisResult, EngineError
from growth.outreach.models import OutreachReport

__all__ = ["OutreachEngine"]


class OutreachEngine:
    """Sitewide/campaign Outreach Engine (§4.9). Architecture only per spec."""
    
    engine_name = "outreach"
    engine_version = "1.0.0"
    
    def supports(self, request_type: str) -> bool:
        return request_type in ("site", "campaign")
    
    def analyze(self, request: EngineAnalysisRequest) -> Result[EngineAnalysisResult, EngineError]:
        report = OutreachReport(
            site_id=request.target.target_id,
            prospects=[],
            campaigns=[],
            opportunity_scores={},
            computed_at=datetime.now(timezone.utc),
            version=1,
        )
        return Ok(EngineAnalysisResult(
            engine_name=self.engine_name,
            engine_version=self.engine_version,
            target=request.target,
            output=report,
            computed_at=report.computed_at,
        ))
