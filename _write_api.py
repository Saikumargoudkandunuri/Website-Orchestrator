"""Write all Milestone 3 API router files with guaranteed clean UTF-8."""
import os

files = {}

# ── shared/api/routes_engines.py ──────────────────────────────────────────────
files["packages/engines/engines/shared/api/routes_engines.py"] = """\
"""Engine API routers — additive (section 6, section 9 of M3 spec).

Two router groups:
1. Per-engine routers under /engines/{engine-slug}/ — thin delegators to the
   engine service via the EnginesContainer.
2. Full-site audit orchestration under /engines/audit — triggers the
   EngineOrchestrator, returns a job reference, and exposes status/results.
"""
from __future__ import annotations
from typing import Any
from fastapi import APIRouter, Body, HTTPException, Request
from pydantic import BaseModel, Field
from engines.shared.audit_job_repository import AuditJobStatus
from engines.shared.engine_contract import PageTarget, SiteTarget

__all__ = ["build_engines_router"]


def _container(request: Request):
    c = getattr(request.app.state, "engines", None)
    if c is None:
        raise HTTPException(status_code=503, detail="Engines layer not configured.")
    return c


# ── DTOs ──────────────────────────────────────────────────────────────────────

class EngineAnalyzeRequest(BaseModel):
    page_id: str | None = None
    site_id: str | None = None
    capabilities: list[str] | None = None
    options: dict = Field(default_factory=dict)


class AuditRequest(BaseModel):
    site_id: str
    page_id: str | None = None
    capabilities: list[str] | None = None
    options: dict = Field(default_factory=dict)


class AuditStatusResponse(BaseModel):
    job_id: str
    site_id: str
    status: str
    engines_requested: list[str]
    engines_completed: list[str]
    engines_failed: list[str]
    started_at: Any = None
    completed_at: Any = None


class AuditResultsResponse(BaseModel):
    job_id: str
    site_id: str
    status: str
    completed: list[str]
    failed: list[str]
    duration_ms: int | None = None
    result_summary: dict


# ── Engine metadata ───────────────────────────────────────────────────────────

_ENGINE_META = {
    "technical-seo":      {"name": "technical_seo",         "scope": "page"},
    "site-architecture":  {"name": "site_architecture",      "scope": "site"},
    "keyword":            {"name": "keyword_intelligence",   "scope": "page"},
    "content":            {"name": "content_intelligence",   "scope": "page"},
    "competitor":         {"name": "competitor_intelligence","scope": "site"},
    "backlink":           {"name": "backlink_intelligence",  "scope": "site"},
    "topical-authority":  {"name": "topical_authority",      "scope": "site"},
    "seo-scoring":        {"name": "seo_scoring",            "scope": "page"},
    "opportunity":        {"name": "opportunity",            "scope": "site"},
    "recommendation":     {"name": "recommendation",         "scope": "both"},
}


def build_engines_router() -> APIRouter:
    router = APIRouter(prefix="/engines", tags=["engines"])

    # ── Per-engine analyze endpoint ──────────────────────────────────────────

    @router.post("/{engine_slug}/analyze", tags=["engines"])
    def engine_analyze(engine_slug: str, request: Request, body: EngineAnalyzeRequest = Body(default_factory=EngineAnalyzeRequest)):
        """Trigger a single engine analysis for a page or site (section 6)."""
        meta = _ENGINE_META.get(engine_slug)
        if meta is None:
            raise HTTPException(status_code=404, detail=f"Unknown engine {engine_slug!r}.")
        container = _container(request)
        from engines.shared.engine_orchestrator import EngineOrchestrator
        orch = EngineOrchestrator(container)
        site_id = body.site_id or "default"
        target = (
            PageTarget(site_id=site_id, page_id=body.page_id)
            if body.page_id
            else SiteTarget(site_id=site_id)
        )
        result = orch.run_audit(
            site_id,
            target=target,
            capabilities=[meta["name"]],
            options=body.options,
        )
        if meta["name"] in result.failed:
            raise HTTPException(status_code=500, detail=f"Engine {meta['name']} failed.")
        output = result.outputs.get(meta["name"])
        return {"engine": meta["name"], "output": output.output.model_dump() if output else None}

    @router.get("/{engine_slug}/pages/{page_id}", tags=["engines"])
    def engine_get_page(engine_slug: str, page_id: str, request: Request):
        """Return the latest stored output for a page from a per-page engine."""
        meta = _ENGINE_META.get(engine_slug)
        if meta is None or meta["scope"] not in ("page", "both"):
            raise HTTPException(status_code=404, detail=f"Unknown per-page engine {engine_slug!r}.")
        container = _container(request)
        repo = _repo_for(container, meta["name"])
        if repo is None:
            raise HTTPException(status_code=404, detail=f"No repository for {engine_slug!r}.")
        result = repo.get_latest(container.tenant_id, page_id)
        if result is None:
            raise HTTPException(status_code=404, detail=f"No {engine_slug!r} data for page {page_id!r}.")
        return result.model_dump()

    @router.get("/{engine_slug}/sites/{site_id}", tags=["engines"])
    def engine_get_site(engine_slug: str, site_id: str, request: Request):
        """Return the latest stored output for a site from a sitewide engine."""
        meta = _ENGINE_META.get(engine_slug)
        if meta is None or meta["scope"] not in ("site", "both"):
            raise HTTPException(status_code=404, detail=f"Unknown sitewide engine {engine_slug!r}.")
        container = _container(request)
        repo = _repo_for(container, meta["name"])
        if repo is None:
            raise HTTPException(status_code=404, detail=f"No repository for {engine_slug!r}.")
        result = repo.get_latest(container.tenant_id, site_id)
        if result is None:
            raise HTTPException(status_code=404, detail=f"No {engine_slug!r} data for site {site_id!r}.")
        return result.model_dump()

    @router.get("/{engine_slug}/versions/{scope_id}", tags=["engines"])
    def engine_list_versions(engine_slug: str, scope_id: str, request: Request):
        """List version history for an engine output."""
        meta = _ENGINE_META.get(engine_slug)
        if meta is None:
            raise HTTPException(status_code=404, detail=f"Unknown engine {engine_slug!r}.")
        container = _container(request)
        repo = _repo_for(container, meta["name"])
        if repo is None:
            raise HTTPException(status_code=404, detail=f"No repository for {engine_slug!r}.")
        return repo.list_versions(container.tenant_id, scope_id)

    # ── Full-site audit orchestration ─────────────────────────────────────────

    @router.post("/audit", tags=["engines-audit"])
    def trigger_audit(request: Request, body: AuditRequest = Body(...)):
        """Trigger a full sitewide audit across all (or selected) engines.

        Returns a job reference for polling. The audit runs synchronously in this
        milestone; the response returns when all engines have completed (or failed).
        A future milestone can make this genuinely async via a task queue (the
        AuditJob model and status/results endpoints are already designed for that).
        """
        container = _container(request)
        from engines.shared.engine_orchestrator import EngineOrchestrator
        orch = EngineOrchestrator(container)
        target = (
            PageTarget(site_id=body.site_id, page_id=body.page_id)
            if body.page_id
            else SiteTarget(site_id=body.site_id)
        )
        result = orch.run_audit(
            body.site_id,
            target=target,
            capabilities=body.capabilities,
            options=body.options,
        )
        return {
            "job_id": result.job_id,
            "site_id": result.site_id,
            "status": result.status.value,
            "completed": sorted(result.completed),
            "failed": result.failed,
            "duration_ms": result.duration_ms,
        }

    @router.get("/audit/{job_id}/status", response_model=AuditStatusResponse, tags=["engines-audit"])
    def audit_status(job_id: str, request: Request):
        """Return the current status of an audit job (section 9)."""
        container = _container(request)
        job = container.audit_job_repo.get(container.tenant_id, job_id)
        if job is None:
            raise HTTPException(status_code=404, detail=f"Audit job {job_id!r} not found.")
        return AuditStatusResponse(
            job_id=job.id,
            site_id=job.site_id,
            status=job.status.value,
            engines_requested=job.engines_requested,
            engines_completed=job.engines_completed,
            engines_failed=job.engines_failed,
            started_at=job.started_at,
            completed_at=job.completed_at,
        )

    @router.get("/audit/{job_id}/results", response_model=AuditResultsResponse, tags=["engines-audit"])
    def audit_results(job_id: str, request: Request):
        """Return the aggregated results of a completed audit job (section 9)."""
        container = _container(request)
        job = container.audit_job_repo.get(container.tenant_id, job_id)
        if job is None:
            raise HTTPException(status_code=404, detail=f"Audit job {job_id!r} not found.")
        if job.status not in (AuditJobStatus.COMPLETED, AuditJobStatus.PARTIAL):
            raise HTTPException(status_code=202, detail=f"Audit {job_id!r} is {job.status.value}; results not yet available.")
        return AuditResultsResponse(
            job_id=job.id,
            site_id=job.site_id,
            status=job.status.value,
            completed=job.engines_completed,
            failed=job.engines_failed,
            duration_ms=job.result_summary.get("duration_ms"),
            result_summary=job.result_summary,
        )

    return router


def _repo_for(container, engine_name: str):
    mapping = {
        "technical_seo": container.technical_seo_repo,
        "site_architecture": container.site_arch_repo,
        "keyword_intelligence": container.keyword_repo,
        "content_intelligence": container.content_repo,
        "competitor_intelligence": container.competitor_repo,
        "backlink_intelligence": container.backlink_repo,
        "topical_authority": container.topical_authority_repo,
        "seo_scoring": container.seo_score_repo,
        "opportunity": container.opportunity_repo,
        "recommendation": container.recommendation_repo,
    }
    return mapping.get(engine_name)
"""

files["packages/engines/engines/shared/api/__init__.py"] = """\
"""Engines API layer — shared router factory."""
from engines.shared.api.routes_engines import build_engines_router
__all__ = ["build_engines_router"]
"""

# ── Per-engine api/__init__.py stubs (each just re-exports the shared router) ─
ENGINE_SLUGS = [
    "technical_seo", "site_architecture", "keyword_intelligence",
    "content_intelligence", "competitor_intelligence", "backlink_intelligence",
    "topical_authority", "seo_scoring", "opportunity", "recommendation",
]
for slug in ENGINE_SLUGS:
    files[f"packages/engines/engines/{slug}/api/__init__.py"] = f"""\
"""Engine-specific API stub — routing is handled by the shared engine router."""
__all__: list[str] = []
"""

for path, content in files.items():
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(content.encode("utf-8"))
    print("written:", path)

print("done")
