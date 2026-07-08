"""FastAPI Router endpoints for System 5 Collaboration Platform."""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from saas.collaboration.models import Thread, Comment, DecisionLog, Notification
from saas.collaboration.services import ThreadService, DecisionLogService, NotificationService

__all__ = ["build_collaboration_router"]


class ThreadCreateRequest(BaseModel):
    target_node_id: str
    title: str


class CommentCreateRequest(BaseModel):
    author: str
    content: str


class DecisionCreateRequest(BaseModel):
    goal_id: str
    actor: str
    rationale: str
    votes: dict[str, Any] = {}


def build_collaboration_router(
    threads: ThreadService,
    decisions: DecisionLogService,
    notifications: NotificationService,
) -> APIRouter:
    router = APIRouter(prefix="/v1/collab", tags=["Collaboration Platform"])

    @router.post("/threads", response_model=Thread)
    def create_thread(req: ThreadCreateRequest, tenant_id: str) -> Thread:
        return threads.start_thread(tenant_id, req.target_node_id, req.title)

    @router.get("/threads")
    def list_threads(target_node_id: str, tenant_id: str) -> list[Thread]:
        return threads._repo.list_threads(tenant_id, target_node_id)

    @router.post("/threads/{id}/comments", response_model=Comment)
    def add_comment(id: str, req: CommentCreateRequest, tenant_id: str) -> Comment:
        return threads.add_comment(tenant_id, id, req.author, req.content)

    @router.get("/threads/{id}/comments", response_model=list[Comment])
    def list_comments(id: str, tenant_id: str) -> list[Comment]:
        return threads._repo.list_comments(tenant_id, id)

    @router.get("/decisions", response_model=list[DecisionLog])
    def list_decisions(tenant_id: str) -> list[DecisionLog]:
        return decisions._repo.list_decisions(tenant_id)

    @router.post("/decisions", response_model=DecisionLog)
    def create_decision(req: DecisionCreateRequest, tenant_id: str) -> DecisionLog:
        return decisions.log_decision(tenant_id, req.goal_id, req.actor, req.rationale, req.votes)

    @router.get("/notifications", response_model=list[Notification])
    def list_notifications(user_id: str, tenant_id: str) -> list[Notification]:
        return notifications._repo.list_notifications(tenant_id, user_id)

    return router
