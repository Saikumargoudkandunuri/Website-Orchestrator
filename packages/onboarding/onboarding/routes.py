"""Onboarding REST API routes.

Thin FastAPI handlers delegating to the onboarding services (mirrors the
API_Surface convention). All handlers are tenant-scoped via the injected
``tenant_id``. Errors from the services are mapped to explicit HTTP responses.

Endpoints
---------
* ``/v1/workspaces``      GET, POST, PUT, DELETE
* ``/v1/projects``        GET, POST, PUT, DELETE
* ``/v1/websites``        GET, POST, PUT, DELETE
* ``/v1/connections``     GET, POST, DELETE
* ``POST /v1/connections/verify``
* ``POST /v1/connections/reconnect``
* ``POST /v1/connections/disconnect``
* ``POST /v1/websites/{id}/detect``
* ``POST /v1/websites/{id}/discover-integrations``
* ``POST /v1/crawl``
* ``POST /v1/build-digital-twin``
* ``GET  /v1/dashboard/live``
* ``GET  /v1/onboarding/audit``
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from onboarding.schemas import (
    ConnectionCreate,
    ConnectionRead,
    ConnectionVerifyRequest,
    CrawlRequest,
    DashboardLive,
    ProjectCreate,
    ProjectRead,
    ProjectUpdate,
    WebsiteCreate,
    WebsiteGroupCreate,
    WebsiteGroupRead,
    WebsiteRead,
    WebsiteUpdate,
    WorkspaceCreate,
    WorkspaceRead,
    WorkspaceUpdate,
    BuildDigitalTwinRequest,
    OnboardingAuditRead,
)
from onboarding.services import OnboardingError, OnboardingOrchestrator

__all__ = ["build_onboarding_router"]

#: Maps an :class:`OnboardingError` to a 4xx/5xx status.
_STATUS_BY_ERROR = {
    "OnboardingError": 400,
}


def build_onboarding_router(
    *,
    workspace_service: Any,
    project_service: Any,
    website_service: Any,
    connection_service: Any,
    orchestrator: OnboardingOrchestrator,
    tenant_id: str,
) -> APIRouter:
    """Build the onboarding router wired to the provided services."""
    router = APIRouter(prefix="/v1", tags=["onboarding"])

    def _tenant() -> str:
        return tenant_id

    def _handle(exc: Exception) -> HTTPException:
        if isinstance(exc, OnboardingError):
            return HTTPException(status_code=400, detail=str(exc))
        return HTTPException(status_code=500, detail=str(exc))

    # --- Workspaces -----------------------------------------------------------

    @router.get("/workspaces", response_model=list[WorkspaceRead])
    def list_workspaces(tenant: str = Depends(_tenant)) -> list[dict]:
        return workspace_service.list(tenant)

    @router.post("/workspaces", response_model=WorkspaceRead, status_code=201)
    def create_workspace(
        body: WorkspaceCreate, tenant: str = Depends(_tenant)
    ) -> dict:
        try:
            return workspace_service.create(
                tenant, name=body.name, description=body.description
            )
        except Exception as exc:  # noqa: BLE001
            raise _handle(exc)

    @router.put("/workspaces/{workspace_id}", response_model=WorkspaceRead)
    def update_workspace(
        workspace_id: str, body: WorkspaceUpdate, tenant: str = Depends(_tenant)
    ) -> dict:
        try:
            row = workspace_service.update(
                tenant, workspace_id, **body.model_dump(exclude_unset=True)
            )
            if row is None:
                raise HTTPException(status_code=404, detail="Workspace not found")
            return row
        except HTTPException:
            raise
        except Exception as exc:  # noqa: BLE001
            raise _handle(exc)

    @router.delete("/workspaces/{workspace_id}", status_code=204)
    def delete_workspace(workspace_id: str, tenant: str = Depends(_tenant)) -> None:
        if not workspace_service.delete(tenant, workspace_id):
            raise HTTPException(status_code=404, detail="Workspace not found")

    # --- Projects -------------------------------------------------------------

    @router.get("/projects", response_model=list[ProjectRead])
    def list_projects(
        workspace_id: str | None = None, tenant: str = Depends(_tenant)
    ) -> list[dict]:
        return project_service.list(tenant, workspace_id)

    @router.post("/projects", response_model=ProjectRead, status_code=201)
    def create_project(body: ProjectCreate, tenant: str = Depends(_tenant)) -> dict:
        try:
            return project_service.create(
                tenant,
                workspace_id=body.workspace_id,
                name=body.name,
                description=body.description,
            )
        except Exception as exc:  # noqa: BLE001
            raise _handle(exc)

    @router.put("/projects/{project_id}", response_model=ProjectRead)
    def update_project(
        project_id: str, body: ProjectUpdate, tenant: str = Depends(_tenant)
    ) -> dict:
        try:
            row = project_service.update(
                tenant, project_id, **body.model_dump(exclude_unset=True)
            )
            if row is None:
                raise HTTPException(status_code=404, detail="Project not found")
            return row
        except HTTPException:
            raise
        except Exception as exc:  # noqa: BLE001
            raise _handle(exc)

    @router.delete("/projects/{project_id}", status_code=204)
    def delete_project(project_id: str, tenant: str = Depends(_tenant)) -> None:
        if not project_service.delete(tenant, project_id):
            raise HTTPException(status_code=404, detail="Project not found")

    # --- Website groups -------------------------------------------------------

    @router.post("/website-groups", response_model=WebsiteGroupRead, status_code=201)
    def create_group(body: WebsiteGroupCreate, tenant: str = Depends(_tenant)) -> dict:
        try:
            return orchestrator._repo.create_group(  # noqa: SLF001 - convenience
                tenant,
                project_id=body.project_id,
                name=body.name,
                description=body.description,
            )
        except Exception as exc:  # noqa: BLE001
            raise _handle(exc)

    # --- Websites -------------------------------------------------------------

    @router.get("/websites", response_model=list[WebsiteRead])
    def list_websites(
        workspace_id: str | None = None,
        project_id: str | None = None,
        group_id: str | None = None,
        tenant: str = Depends(_tenant),
    ) -> list[dict]:
        # Internal-only: still supports the multi-tenant persistence model, but
        # the product surface (my-website below) is what the console/UX uses —
        # nothing calls this to render an "add/switch website" control.
        return website_service.list(
            tenant, workspace_id=workspace_id, project_id=project_id, group_id=group_id
        )

    @router.get("/websites/my-website", response_model=WebsiteRead | None)
    def my_website(tenant: str = Depends(_tenant)) -> dict | None:
        """Return this account's single connected website, or ``null`` before
        onboarding connects one (Milestone 5 — one account = one website).

        The dashboard calls this once on login to auto-load the account's
        website; there is never a list, switcher, or "add another website"
        control anywhere in the product surface.
        """
        return website_service.get_my_website(tenant) or None

    @router.post("/websites", response_model=WebsiteRead, status_code=201)
    def create_website(body: WebsiteCreate, tenant: str = Depends(_tenant)) -> dict:
        """Connect this account's one website (Milestone 5 — one account = one
        website). Rejects with 400 if the account already has a connected
        website; disconnect it first via ``DELETE /websites/{id}``."""
        try:
            return website_service.create(
                tenant,
                workspace_id=body.workspace_id,
                project_id=body.project_id,
                group_id=body.group_id,
                name=body.name,
                url=body.url,
                display_name=body.display_name,
                environment=body.environment.value,
                website_type=body.website_type.value,
            )
        except Exception as exc:  # noqa: BLE001
            raise _handle(exc)

    @router.put("/websites/{website_id}", response_model=WebsiteRead)
    def update_website(
        website_id: str, body: WebsiteUpdate, tenant: str = Depends(_tenant)
    ) -> dict:
        try:
            changes = body.model_dump(exclude_unset=True)
            if "environment" in changes and changes["environment"] is not None:
                changes["environment"] = changes["environment"].value
            if "website_type" in changes and changes["website_type"] is not None:
                changes["website_type"] = changes["website_type"].value
            if "approval_mode" in changes and changes["approval_mode"] is not None:
                changes["approval_mode"] = changes["approval_mode"].value
            if "agent_config" in changes and changes["agent_config"] is not None:
                changes["agent_config"] = changes["agent_config"].model_dump()
            row = website_service.update(tenant, website_id, **changes)
            if row is None:
                raise HTTPException(status_code=404, detail="Website not found")
            return row
        except HTTPException:
            raise
        except Exception as exc:  # noqa: BLE001
            raise _handle(exc)

    @router.delete("/websites/{website_id}", status_code=204)
    def delete_website(website_id: str, tenant: str = Depends(_tenant)) -> None:
        if not website_service.delete(tenant, website_id):
            raise HTTPException(status_code=404, detail="Website not found")

    # --- Connections ----------------------------------------------------------

    @router.get("/connections", response_model=list[ConnectionRead])
    def list_connections(website_id: str, tenant: str = Depends(_tenant)) -> list[dict]:
        return connection_service.list(tenant, website_id)

    @router.post("/connections", response_model=ConnectionRead, status_code=201)
    def create_connection(body: ConnectionCreate, tenant: str = Depends(_tenant)) -> dict:
        try:
            return connection_service.create(
                tenant,
                website_id=body.website_id,
                connection_type=body.connection_type.value,
                credential=body.credential,
                connection_meta=body.connection_meta,
            )
        except Exception as exc:  # noqa: BLE001
            raise _handle(exc)

    @router.post("/connections/verify")
    def verify_connection(
        body: ConnectionVerifyRequest, tenant: str = Depends(_tenant)
    ) -> dict:
        try:
            return connection_service.verify(
                tenant,
                website_id=body.website_id,
                connection_type=body.connection_type.value,
                credential=body.credential,
                connection_meta=body.connection_meta,
            )
        except Exception as exc:  # noqa: BLE001
            raise _handle(exc)

    @router.post("/connections/reconnect")
    def reconnect_connection(
        body: ConnectionVerifyRequest, tenant: str = Depends(_tenant)
    ) -> dict:
        try:
            # Reconnect by website: find the latest connection and re-verify.
            conns = connection_service.list(tenant, body.website_id)
            if not conns:
                raise HTTPException(status_code=404, detail="No connection to reconnect")
            return connection_service.reconnect(tenant, conns[-1]["id"])
        except HTTPException:
            raise
        except Exception as exc:  # noqa: BLE001
            raise _handle(exc)

    @router.post("/connections/disconnect")
    def disconnect_connection(
        body: ConnectionVerifyRequest, tenant: str = Depends(_tenant)
    ) -> dict:
        conns = connection_service.list(tenant, body.website_id)
        if not conns:
            raise HTTPException(status_code=404, detail="No connection to disconnect")
        ok = connection_service.disconnect(tenant, conns[-1]["id"])
        return {"disconnected": ok}

    @router.delete("/connections/{connection_id}", status_code=204)
    def delete_connection(connection_id: str, tenant: str = Depends(_tenant)) -> None:
        if not connection_service.disconnect(tenant, connection_id):
            raise HTTPException(status_code=404, detail="Connection not found")

    # --- Detection / integrations / crawl / twin ------------------------------

    @router.post("/websites/{website_id}/detect")
    def detect_website(website_id: str, tenant: str = Depends(_tenant)) -> dict:
        try:
            result = orchestrator.detect_website(website_id)
            return result.to_website_fields()
        except OnboardingError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        except Exception as exc:  # noqa: BLE001
            raise _handle(exc)

    @router.post("/websites/{website_id}/discover-integrations")
    def discover_integrations(website_id: str, tenant: str = Depends(_tenant)) -> list[dict]:
        try:
            return orchestrator.discover_integrations(website_id)
        except OnboardingError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        except Exception as exc:  # noqa: BLE001
            raise _handle(exc)

    @router.post("/crawl")
    def crawl(body: CrawlRequest, tenant: str = Depends(_tenant)) -> dict:
        try:
            return orchestrator.run_initial_crawl(body.website_id, body.max_pages)
        except OnboardingError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        except Exception as exc:  # noqa: BLE001
            raise _handle(exc)

    @router.post("/build-digital-twin")
    def build_twin(body: BuildDigitalTwinRequest, tenant: str = Depends(_tenant)) -> dict:
        try:
            return orchestrator.build_digital_twin(body.website_id)
        except OnboardingError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        except Exception as exc:  # noqa: BLE001
            raise _handle(exc)

    # --- Dashboard ------------------------------------------------------------

    @router.get("/dashboard/live", response_model=DashboardLive)
    def dashboard_live(website_id: str, tenant: str = Depends(_tenant)) -> dict:
        website = website_service.get(tenant, website_id)
        if website is None:
            raise HTTPException(status_code=404, detail="Website not found")
        # Aggregate live counts from the most recent crawl (cached in the
        # orchestrator) when available.
        pages = posts = media = issues = pending = 0
        crawled = orchestrator._crawled_pages.get(website_id)  # noqa: SLF001
        if crawled:
            pages = len(crawled)
            media = sum(len(getattr(p, "images", []) or []) for p in crawled)
        return DashboardLive(
            website_id=website["id"],
            name=website["name"],
            url=website["url"],
            status=website["status"],
            environment=website["environment"],
            builder=website["builder"],
            theme=website["theme"],
            cms=website["cms"],
            plugins=website["plugins"],
            pages=pages,
            posts=posts,
            media=media,
            issues=issues,
            pending_fixes=pending,
            last_crawl=website["last_crawled_at"],
            automation_status="active" if website["automation_enabled"] else "inactive",
            ai_status="enabled" if website["ai_enabled"] else "disabled",
            memory_status="enabled" if website["memory_enabled"] else "disabled",
        ).model_dump()

    # --- Audit ----------------------------------------------------------------

    @router.get("/onboarding/audit", response_model=list[OnboardingAuditRead])
    def audit(website_id: str | None = None, tenant: str = Depends(_tenant)) -> list[dict]:
        return [
            _audit_to_dict(a)
            for a in orchestrator._repo.list_audit(tenant, website_id)
        ]

    return router


def _audit_to_dict(row: Any) -> dict:
    out: dict[str, Any] = {}
    for key in type(row).__mapper__.columns.keys():
        value = getattr(row, key)
        if hasattr(value, "isoformat"):
            value = value.isoformat()
        out[key] = value
    return out
