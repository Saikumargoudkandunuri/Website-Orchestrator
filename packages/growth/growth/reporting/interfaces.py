"""Reporting Engine interface (§4.6)."""
from __future__ import annotations
import time
from datetime import datetime, timezone
from core.results import Err, Ok, Result
from growth.shared.generator_contract import (
    GenerationRequest,
    GeneratedArtifact,
    GenerationError,
)
from growth.reporting.models import ReportArtifact

__all__ = ["ReportingEngine"]


class ReportingEngine:
    """
    Sitewide/per-client Reporting Engine (§4.6).
    
    GeneratorEngine (NOT analytical Engine) - output is report document, not raw analysis.
    ZERO independent metric computation - pure synthesis/presentation layer.
    """

    engine_name = "reporting"
    engine_version = "1.0.0"

    def supports(self, request_type: str) -> bool:
        supported = {
            "executive", "seo", "technical", "content", "growth",
            "keyword", "backlink", "local_seo", "reputation",
        }
        return request_type in supported

    def generate(
        self, request: GenerationRequest
    ) -> Result[GeneratedArtifact, GenerationError]:
        """Generate report. Service does actual work."""
        start = time.perf_counter()
        try:
            # The concrete service renders and persists report artifacts.
            artifact = GeneratedArtifact(
                id=f"report-{request.generation_type}-{int(datetime.now(timezone.utc).timestamp())}",
                generation_type=request.generation_type,
                content={"status": "delegated_to_reporting_service"},
                computed_at=datetime.now(timezone.utc),
            )
        except Exception as exc:
            return Err(GenerationError(
                message=f"Reporting failed: {exc}",
                generation_type=request.generation_type,
            ))
        duration_ms = int((time.perf_counter() - start) * 1000)
        return Ok(artifact)
