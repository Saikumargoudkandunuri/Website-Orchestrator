"""API router for agentic reflection and learning (M6 Build Phase E)."""
from __future__ import annotations

from typing import Any
from fastapi import APIRouter, HTTPException, Request

from agentic.reflection.wiring import ReflectionContainer


def build_reflection_router() -> APIRouter:
    """Build the reflection and learning API router."""
    router = APIRouter(prefix="/agentic", tags=["agentic-reflection"])
    
    def _reflection(request: Request) -> ReflectionContainer:
        container = getattr(request.app.state, "agentic_reflection", None)
        if container is None:
            raise HTTPException(503, "Agentic reflection container is not available.")
        return container

    @router.post("/reflection/run")
    def run_reflection(execution_id: str, steps: list[dict[str, Any]], request: Request) -> dict[str, Any]:
        container = _reflection(request)
        try:
            return container.reflection_engine.reflect_on_execution(container.tenant_id, execution_id, steps)
        except Exception as e:
            raise HTTPException(400, str(e))

    @router.get("/reflection/{execution_id}")
    def get_reflection(execution_id: str, request: Request) -> dict[str, Any]:
        container = _reflection(request)
        res = container.reflection_repo.get_by_execution(container.tenant_id, execution_id)
        if not res:
            raise HTTPException(404, f"Reflection for execution '{execution_id}' not found.")
        return res

    @router.get("/learning/provider-scores")
    def get_provider_scores(request: Request) -> list[dict[str, Any]]:
        container = _reflection(request)
        return container.provider_score_repo.get_scores(container.tenant_id)

    @router.get("/learning/tool-scores")
    def get_tool_scores(request: Request) -> list[dict[str, Any]]:
        container = _reflection(request)
        return container.tool_score_repo.get_scores(container.tenant_id)

    @router.get("/learning/experience")
    def get_experience_summary(request: Request) -> dict[str, Any]:
        container = _reflection(request)
        return container.experience_analyzer.analyze_experiences(container.tenant_id)

    @router.get("/learning/confidence")
    def get_confidence_calibration(category: str, request: Request) -> dict[str, Any]:
        container = _reflection(request)
        res = container.confidence_repo.get_calibration(container.tenant_id, category)
        if not res:
            raise HTTPException(404, f"Confidence calibration for category '{category}' not found.")
        return res

    return router
