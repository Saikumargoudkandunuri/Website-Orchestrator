"""FastAPI Router endpoints for System 6 AI Experience Layer."""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from saas.copilot.models import PromptTemplate, AIExplanation
from saas.copilot.services import CopilotService, ContextCollectorService, ExplanationEngineService

__all__ = ["build_copilot_router"]


class ChatRequest(BaseModel):
    session_id: str
    user_id: str
    prompt: str
    site_id: str
    focus_page_id: str | None = None


class PromptCreateRequest(BaseModel):
    name: str
    template_text: str
    description: str | None = None


def build_copilot_router(
    copilot: CopilotService,
    collector: ContextCollectorService,
    explanations: ExplanationEngineService,
) -> APIRouter:
    router = APIRouter(prefix="/v1/copilot", tags=["AI Experience"])

    @router.post("/chat")
    def copilot_chat(req: ChatRequest, tenant_id: str) -> dict[str, str]:
        # Simple REST return (streaming proxies over SSE can wrap this payload)
        ctx = collector.collect_context(tenant_id, req.site_id, req.focus_page_id)
        reply = copilot.generate_chat_response(
            tenant_id=tenant_id,
            session_id=req.session_id,
            user_id=req.user_id,
            prompt=req.prompt,
            context=ctx,
        )
        return {"response": reply}

    @router.get("/reasoning/{goal_id}", response_model=AIExplanation)
    def get_reasoning_explanation(goal_id: str, tenant_id: str) -> AIExplanation:
        exp = explanations._repo.get_explanation(tenant_id, goal_id)
        if not exp:
            # compile placeholder if none exists
            exp = explanations.compile_reasoning_graph(tenant_id, goal_id, None)
        return exp

    @router.post("/prompts", response_model=PromptTemplate)
    def create_prompt_template(req: PromptCreateRequest, tenant_id: str) -> PromptTemplate:
        from uuid import uuid4
        tmpl = PromptTemplate(
            id=str(uuid4()),
            tenant_id=tenant_id,
            name=req.name,
            template_text=req.template_text,
            description=req.description,
        )
        explanations._repo.save_template(tmpl)
        return tmpl

    @router.get("/prompts", response_model=list[PromptTemplate])
    def list_prompt_templates(tenant_id: str) -> list[PromptTemplate]:
        return explanations._repo.list_templates(tenant_id)

    return router
