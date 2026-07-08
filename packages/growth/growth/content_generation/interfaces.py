"""Content Generation Engine interface (§4.1)."""
from __future__ import annotations
import time
from datetime import datetime, timezone
from core.results import Err, Ok, Result
from growth.errors import GrowthGenerationError
from growth.shared.generator_contract import (
    GenerationRequest,
    GeneratedArtifact,
    GenerationError,
)

__all__ = ["ContentGenerationEngine"]


class ContentGenerationEngine:
    """Per-page/per-new-asset Content Generation Engine (§4.1)."""

    engine_name = "content_generation"
    engine_version = "1.0.0"

    def supports(self, request_type: str) -> bool:
        supported = {
            "blog_post", "landing_page", "service_page", "location_page",
            "product_page", "category_page", "faq_page", "comparison_page",
            "pillar_page", "cluster_page",
        }
        return request_type in supported

    def generate(
        self, request: GenerationRequest
    ) -> Result[GeneratedArtifact, GenerationError]:
        """Generate content. This is a thin wrapper for API routing."""
        start = time.perf_counter()
        try:
            # The concrete service supplies the governed ContentAsset payload.
            artifact = GeneratedArtifact(
                id=f"gen-{request.generation_type}-{int(datetime.now(timezone.utc).timestamp())}",
                generation_type=request.generation_type,
                content={"status": "delegated_to_content_generation_service"},
                computed_at=datetime.now(timezone.utc),
            )
        except Exception as exc:
            return Err(GenerationError(
                message=f"ContentGeneration failed: {exc}",
                generation_type=request.generation_type,
            ))
        duration_ms = int((time.perf_counter() - start) * 1000)
        return Ok(artifact)
