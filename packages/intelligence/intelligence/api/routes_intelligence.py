"""Additive FastAPI router for the SEO Intelligence Layer (§10, §13.6).

Mounted alongside — never replacing — Milestone 1's routers. Handlers are thin:
they resolve the :class:`IntelligenceContainer` from ``app.state`` and delegate to
the orchestrator/repositories. Tenant is taken from the container (the router
does not import Milestone 1's API package, preserving the one-directional
dependency).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Body, HTTPException, Request

from intelligence.api.dto.analysis_request_dto import AnalyzeRequest, PatchFieldsRequest
from intelligence.api.dto.analysis_response_dto import AnalyzeResponse
from intelligence.api.dto.knowledge_object_dto import VersionSummary
from intelligence.api.wiring import IntelligenceContainer
from intelligence.field_paths import get_by_path, set_by_path
from intelligence.models.ai_invocation import AIInvocation
from intelligence.models.content_intelligence import ContentScore
from intelligence.models.knowledge_object import FieldOverride, KnowledgeObject
from intelligence.models.metadata_intelligence import OverrideSource
from intelligence.validation.validation_pipeline import is_writable

__all__ = ["build_intelligence_router"]


def _container(request: Request) -> IntelligenceContainer:
    container = getattr(request.app.state, "intelligence", None)
    if container is None:  # pragma: no cover - defensive
        raise HTTPException(status_code=503, detail="Intelligence layer not configured.")
    return container


def build_intelligence_router() -> APIRouter:
    router = APIRouter(prefix="/intelligence", tags=["intelligence"])

    @router.post("/pages/{page_id}/analyze", response_model=AnalyzeResponse)
    def analyze(page_id: str, request: Request, body: AnalyzeRequest = Body(default_factory=AnalyzeRequest)) -> AnalyzeResponse:
        """Run analysis and create a new KnowledgeObject version (§10)."""
        container = _container(request)
        ko = container.orchestrator().run_for_snapshot(
            page_id,
            capabilities=body.capabilities,
            force_regenerate_overrides=body.force_regenerate_overrides,
        )
        if ko is None:
            raise HTTPException(
                status_code=404,
                detail=f"No crawl snapshot for page {page_id!r}; crawl/ingest it first.",
            )
        return AnalyzeResponse(page_id=ko.page_id, version=ko.version, knowledge_object=ko)

    @router.get("/pages/{page_id}", response_model=KnowledgeObject)
    def get_latest(page_id: str, request: Request) -> KnowledgeObject:
        """Return the latest KnowledgeObject for the page (§10)."""
        container = _container(request)
        ko = container.knowledge_repo.get_latest(container.tenant_id, page_id)
        if ko is None:
            raise HTTPException(status_code=404, detail=f"No KnowledgeObject for page {page_id!r}.")
        return ko

    @router.get("/pages/{page_id}/versions", response_model=list[VersionSummary])
    def list_versions(page_id: str, request: Request) -> list[VersionSummary]:
        """List version history without full payloads (§10)."""
        container = _container(request)
        return [
            VersionSummary(version=v.version, created_at=v.created_at, crawl_id=v.crawl_id)
            for v in container.knowledge_repo.list_versions(container.tenant_id, page_id)
        ]

    @router.get("/pages/{page_id}/versions/{version}", response_model=KnowledgeObject)
    def get_version(page_id: str, version: int, request: Request) -> KnowledgeObject:
        """Return a specific historical KnowledgeObject version (§10)."""
        container = _container(request)
        ko = container.knowledge_repo.get_version(container.tenant_id, page_id, version)
        if ko is None:
            raise HTTPException(
                status_code=404, detail=f"No version {version} for page {page_id!r}."
            )
        return ko

    @router.get("/pages/{page_id}/ai-invocations", response_model=list[AIInvocation])
    def list_ai_invocations(page_id: str, request: Request) -> list[AIInvocation]:
        """Return the AIInvocation audit records for the page (§5.3, §10)."""
        container = _container(request)
        return container.invocation_repo.list_for_page(container.tenant_id, page_id)

    @router.get("/pages/{page_id}/content-score", response_model=ContentScore)
    def get_content_score(page_id: str, request: Request) -> ContentScore:
        """Return just the ContentScore for lightweight editor UI (§13.6)."""
        container = _container(request)
        ko = container.knowledge_repo.get_latest(container.tenant_id, page_id)
        if ko is None:
            raise HTTPException(status_code=404, detail=f"No KnowledgeObject for page {page_id!r}.")
        return ko.content_intelligence.content_score

    @router.patch("/pages/{page_id}/fields", response_model=KnowledgeObject)
    def patch_fields(page_id: str, request: Request, body: PatchFieldsRequest) -> KnowledgeObject:
        """Apply human field overrides as a new, audited version (§13.6).

        Respects ``immutable_fields``: a locked path is rejected (409) exactly as
        an AI proposal would be. Accepted edits set ``override_source = "human"``
        and are recorded in the override registry.
        """
        container = _container(request)
        latest = container.knowledge_repo.get_latest(container.tenant_id, page_id)
        if latest is None:
            raise HTTPException(status_code=404, detail=f"No KnowledgeObject for page {page_id!r}.")

        locked = [p for p in body.fields if not is_writable(p, latest.immutable_fields)]
        if locked:
            raise HTTPException(
                status_code=409,
                detail=f"Rejected: field path(s) are immutable: {', '.join(sorted(locked))}",
            )

        new_version = container.knowledge_repo.next_version(container.tenant_id, page_id)
        now = datetime.now(timezone.utc)
        ko = latest.model_copy(deep=True)
        ko.id = uuid.uuid4().hex
        ko.version = new_version
        ko.created_at = now

        applied: list[str] = []
        for path, value in body.fields.items():
            if not set_by_path(ko, path, value):
                raise HTTPException(status_code=422, detail=f"Unknown field path: {path!r}")
            override = FieldOverride(source="human", overridden_at=now, overridden_by=body.actor)
            ko.overrides[path] = override
            parent = get_by_path(ko, path.rsplit(".", 1)[0]) if "." in path else None
            if parent is not None and hasattr(parent, "override_source"):
                parent.override_source = OverrideSource.HUMAN
                parent.overridden_at = now
                parent.overridden_by = body.actor
            applied.append(path)

        return container.knowledge_repo.save(container.tenant_id, ko)

    return router
