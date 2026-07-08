"""API router for cognitive memory (M6 Build Phase C)."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request

from agentic.memory.models import (
    ExperienceEpisode,
    GoalMemoryRecord,
    ReflectionLesson,
    SemanticFact,
    WorkflowTemplate,
)
from agentic.memory.wiring import MemoryContainer


def build_memory_router() -> APIRouter:
    """Build the cognitive memory API router."""
    router = APIRouter(prefix="/agentic/memory", tags=["agentic-memory"])
    
    def _memory(request: Request) -> MemoryContainer:
        container = getattr(request.app.state, "agentic_memory", None)
        if container is None:
            raise HTTPException(503, "Agentic memory container is not available.")
        return container

    @router.get("/goals")
    def list_goals(request: Request) -> list[dict[str, Any]]:
        container = _memory(request)
        records = container.goal.list_goal_records(container.tenant_id)
        return [r.model_dump(mode="json") for r in records]

    @router.get("/goals/{goal_id}")
    def get_goal(goal_id: str, request: Request) -> dict[str, Any]:
        container = _memory(request)
        record = container.goal.get_goal_record(container.tenant_id, goal_id)
        if not record:
            raise HTTPException(404, f"Goal record {goal_id} not found.")
        return record.model_dump(mode="json")

    @router.post("/goals")
    def save_goal(record_data: dict[str, Any], request: Request) -> dict[str, Any]:
        container = _memory(request)
        # Add tenant mapping
        record_data["tenant_id"] = container.tenant_id
        # Build model safely
        try:
            record = GoalMemoryRecord.model_validate(record_data)
        except Exception as e:
            raise HTTPException(422, f"Invalid GoalMemoryRecord schema: {e}")
            
        container.goal.save_goal_record(record)
        return record.model_dump(mode="json")

    @router.get("/episodes")
    def list_episodes(request: Request) -> list[dict[str, Any]]:
        container = _memory(request)
        episodes = container.episodic.list_episodes(container.tenant_id)
        return [e.model_dump(mode="json") for e in episodes]

    @router.get("/reflections")
    def list_reflections(request: Request) -> list[dict[str, Any]]:
        container = _memory(request)
        lessons = container.reflection.list_lessons(container.tenant_id)
        return [L.model_dump(mode="json") for L in lessons]

    @router.post("/reflections")
    def save_reflection(lesson_data: dict[str, Any], request: Request) -> dict[str, Any]:
        container = _memory(request)
        lesson_data["tenant_id"] = container.tenant_id
        try:
            lesson = ReflectionLesson.model_validate(lesson_data)
        except Exception as e:
            raise HTTPException(422, f"Invalid ReflectionLesson schema: {e}")
            
        container.reflection.record_lesson(lesson)
        return lesson.model_dump(mode="json")

    @router.get("/procedures")
    def list_procedures(request: Request) -> list[dict[str, Any]]:
        # In a real implementation we could list all templates, for now we list by loading named from DB
        # This endpoint is mapped to support procedural lookups
        container = _memory(request)
        # Returns empty list or mocks standard templates for API consistency
        return []

    @router.post("/procedures")
    def save_procedure(template_data: dict[str, Any], request: Request) -> dict[str, Any]:
        container = _memory(request)
        template_data["tenant_id"] = container.tenant_id
        try:
            template = WorkflowTemplate.model_validate(template_data)
        except Exception as e:
            raise HTTPException(422, f"Invalid WorkflowTemplate schema: {e}")
            
        container.procedural.save_template(template)
        return template.model_dump(mode="json")

    @router.get("/semantic")
    def get_semantic(key: str, request: Request) -> dict[str, Any]:
        container = _memory(request)
        fact = container.semantic.get_fact(container.tenant_id, key)
        if not fact:
            raise HTTPException(404, f"Semantic fact for key '{key}' not found.")
        return fact.model_dump(mode="json")

    @router.get("/search")
    def search_memory(query: str, request: Request) -> list[dict[str, Any]]:
        """Search memory coordinates using Manager."""
        container = _memory(request)
        # Simple coordinate lookups based on string matching
        reflections = container.manager.find_relevant_reflections(query)
        return [L.model_dump(mode="json") for L in reflections]

    return router
