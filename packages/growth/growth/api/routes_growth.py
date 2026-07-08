"""Additive FastAPI router for Milestone 4 growth engines."""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from growth.api.wiring import GrowthContainer
from growth.agency_management.models import (
    Client,
    Notification,
    Organization,
    Task,
    Team,
    Workspace,
)
from growth.content_generation.models import ContentGenerationRequest
from growth.auth import GrowthIdentity
from growth.errors import GrowthAuthenticationError
from growth.permissions import PermissionAction, PermissionScope, has_permission
from growth.rank_tracking.models import TrackedKeyword
from growth.reporting.models import BrandingConfig, ReportDefinition, ReportFormat, ReportType
from growth.shared.automation.automation_rule_engine import AutomationRule
from growth.shared.automation.event_bus_interface import DomainEvent

__all__ = ["build_growth_router"]


class DecisionBody(BaseModel):
    actor: str = "system"
    notes: str = ""
    reason: str = ""


class ContentOptimizationAnalyzeBody(BaseModel):
    site_id: str = "default"
    content_intelligence_output: dict[str, Any] = Field(default_factory=dict)
    content_intelligence_section: dict[str, Any] = Field(default_factory=dict)
    keyword_intelligence_section: dict[str, Any] = Field(default_factory=dict)


class LocalSeoAnalyzeBody(BaseModel):
    pages_with_contact_data: list[dict[str, Any]] = Field(default_factory=list)


class RankKeywordBody(BaseModel):
    keyword: str
    page_id: str = ""
    device: str = "desktop"
    geo: str = "US"
    cadence: str = "daily"
    organization_id: str | None = None
    client_id: str | None = None


class RankCaptureBody(BaseModel):
    device: str = "desktop"
    geo: str = "US"


class ReportGenerateBody(BaseModel):
    report_type: str = ReportType.GROWTH
    format: str = ReportFormat.JSON
    schedule: str | None = None
    branding_ref: str = "default"
    source_engine_refs: list[str] = Field(default_factory=lambda: ["seo_scoring", "rank_tracking", "analytics_intelligence"])
    filters: dict[str, Any] = Field(default_factory=dict)
    branding: dict[str, Any] = Field(default_factory=dict)
    organization_id: str | None = None
    client_id: str | None = None


class OrganizationBody(BaseModel):
    organization_id: str | None = None
    name: str
    branding: dict[str, Any] = Field(default_factory=dict)


class ClientBody(BaseModel):
    client_id: str | None = None
    name: str
    contact_email: str | None = None


class TeamBody(BaseModel):
    team_id: str | None = None
    name: str
    members: list[str] = Field(default_factory=list)


class WorkspaceBody(BaseModel):
    workspace_id: str | None = None
    organization_id: str
    user_id: str
    name: str
    client_refs: list[str] = Field(default_factory=list)
    site_refs: list[str] = Field(default_factory=list)
    pinned_dashboards: list[str] = Field(default_factory=list)


class TaskBody(BaseModel):
    task_id: str | None = None
    organization_id: str
    client_id: str
    title: str
    description: str
    referenced_finding_id: str | None = None
    assignee_id: str | None = None
    status: str = "open"


class TaskStatusBody(BaseModel):
    status: str


class NotificationBody(BaseModel):
    notification_id: str | None = None
    organization_id: str
    recipient_id: str
    channel: str = "in_app"
    message: str
    status: str = "pending"


def _container(request: Request) -> GrowthContainer:
    container = getattr(request.app.state, "growth", None)
    if container is None:
        raise HTTPException(status_code=503, detail="Growth layer not configured.")
    return container


def require_growth_access(request: Request) -> GrowthIdentity:
    c = _container(request)
    try:
        identity = c.auth_provider.authenticate(request)
    except GrowthAuthenticationError as exc:
        raise HTTPException(
            status_code=401,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    if identity.tenant_id != c.tenant_id:
        raise HTTPException(
            status_code=401,
            detail="Credential tenant does not match this Growth container.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    request.state.growth_identity = identity
    action, scope = _required_permission(request)
    if not has_permission(identity, action, scope):
        raise HTTPException(
            status_code=403,
            detail=f"Growth role lacks {action.value} permission for {scope.value} scope.",
        )
    return identity


def _required_permission(request: Request) -> tuple[PermissionAction, PermissionScope]:
    path = request.url.path
    method = request.method.upper()
    if path.endswith("/approve"):
        action = PermissionAction.APPROVE
    elif path.endswith("/publish"):
        action = PermissionAction.PUBLISH
    elif method == "DELETE" or _is_admin_path(path, method):
        action = PermissionAction.ADMIN
    elif method in {"GET", "HEAD", "OPTIONS"}:
        action = PermissionAction.READ
    else:
        action = PermissionAction.WRITE
    return action, _permission_scope(path)


def _is_admin_path(path: str, method: str) -> bool:
    return (
        path == "/growth/automation/rules"
        or (path.startswith("/growth/agency/organizations") and method == "POST")
    )


def _permission_scope(path: str) -> PermissionScope:
    if path.startswith("/growth/agency/workspaces"):
        return PermissionScope.WORKSPACE
    if path.startswith("/growth/agency/organizations") and "/clients" not in path:
        return PermissionScope.ORGANIZATION
    if path.startswith("/growth/content-generation"):
        return PermissionScope.WORKSPACE
    return PermissionScope.CLIENT


def _unwrap(result: Any) -> Any:
    if getattr(result, "is_ok", False):
        return result.unwrap()
    if getattr(result, "is_err", False):
        raise HTTPException(status_code=502, detail=str(result.unwrap_err()))
    return result


def build_growth_router() -> APIRouter:
    router = APIRouter(
        prefix="/growth",
        tags=["growth"],
        dependencies=[Depends(require_growth_access)],
    )

    @router.get("/health")
    def growth_health(request: Request) -> dict[str, Any]:
        c = _container(request)
        services = [
            "content_generation",
            "content_optimization",
            "local_seo",
            "reputation",
            "rank_tracking",
            "reporting",
            "analytics",
            "outreach",
            "automation",
            "agency_management",
        ]
        return {
            "status": "ok",
            "tenant_id": c.tenant_id,
            "services": {name: hasattr(c, name) for name in services},
        }

    @router.post("/content-generation/generate")
    def generate_content(body: ContentGenerationRequest, request: Request) -> Any:
        c = _container(request)
        normalized = body.model_copy(update={"tenant_id": c.tenant_id})
        return c.content_generation.generate(normalized)

    @router.get("/content-generation/assets/{asset_id}")
    def get_content_asset(asset_id: str, request: Request) -> Any:
        asset = _container(request).content_asset_repo.get(asset_id)
        if asset is None:
            raise HTTPException(status_code=404, detail=f"Content asset {asset_id!r} not found.")
        return asset

    @router.get("/content-generation/sites/{site_id}/assets")
    def list_content_assets(site_id: str, request: Request) -> Any:
        c = _container(request)
        return c.content_asset_repo.list_by_site(c.tenant_id, site_id)

    @router.post("/content-generation/assets/{asset_id}/submit")
    def submit_content_asset(asset_id: str, request: Request, body: DecisionBody = Body(default_factory=DecisionBody)) -> Any:
        return _container(request).content_generation.submit_for_review(asset_id, body.actor)

    @router.post("/content-generation/assets/{asset_id}/approve")
    def approve_content_asset(asset_id: str, request: Request, body: DecisionBody = Body(default_factory=DecisionBody)) -> Any:
        return _container(request).content_generation.approve(asset_id, body.actor, body.notes)

    @router.post("/content-generation/assets/{asset_id}/reject")
    def reject_content_asset(asset_id: str, request: Request, body: DecisionBody) -> Any:
        return _container(request).content_generation.reject(asset_id, body.actor, body.reason or body.notes)

    @router.post("/content-generation/assets/{asset_id}/publish")
    def publish_content_asset(asset_id: str, request: Request, body: DecisionBody = Body(default_factory=DecisionBody)) -> Any:
        return _container(request).content_generation.publish(asset_id, body.actor)

    @router.post("/content-generation/assets/{asset_id}/verify")
    def verify_content_asset(asset_id: str, request: Request, body: DecisionBody = Body(default_factory=DecisionBody)) -> Any:
        return _container(request).content_generation.verify(asset_id, body.actor)

    @router.post("/content-optimization/pages/{page_id}/analyze")
    def analyze_content_optimization(page_id: str, body: ContentOptimizationAnalyzeBody, request: Request) -> Any:
        c = _container(request)
        report = _unwrap(c.content_optimization.analyze(
            page_id,
            body.content_intelligence_output,
            body.content_intelligence_section,
            body.keyword_intelligence_section,
        ))
        return c.content_optimization_repo.save(c.tenant_id, page_id, report, site_id=body.site_id)

    @router.get("/content-optimization/pages/{page_id}/reports/latest")
    def latest_content_optimization(page_id: str, request: Request) -> Any:
        c = _container(request)
        report = c.content_optimization_repo.get_latest(c.tenant_id, page_id)
        if report is None:
            raise HTTPException(status_code=404, detail="No content optimization report found.")
        return report

    @router.post("/local-seo/sites/{site_id}/analyze")
    def analyze_local_seo(site_id: str, body: LocalSeoAnalyzeBody, request: Request) -> Any:
        c = _container(request)
        report = _unwrap(c.local_seo.analyze(site_id, body.pages_with_contact_data))
        return c.local_seo_repo.save(c.tenant_id, site_id, report)

    @router.get("/local-seo/sites/{site_id}/reports/latest")
    def latest_local_seo(site_id: str, request: Request) -> Any:
        c = _container(request)
        report = c.local_seo_repo.get_latest(c.tenant_id, site_id)
        if report is None:
            raise HTTPException(status_code=404, detail="No local SEO report found.")
        return report

    @router.post("/reputation/sites/{site_id}/analyze")
    def analyze_reputation(site_id: str, request: Request, location_id: str | None = None) -> Any:
        c = _container(request)
        report = _unwrap(c.reputation.analyze(site_id, location_id))
        return c.reputation_repo.save(c.tenant_id, site_id, report)

    @router.get("/reputation/sites/{site_id}/reports/latest")
    def latest_reputation(site_id: str, request: Request) -> Any:
        c = _container(request)
        report = c.reputation_repo.get_latest(c.tenant_id, site_id)
        if report is None:
            raise HTTPException(status_code=404, detail="No reputation report found.")
        return report

    @router.post("/rank-tracking/sites/{site_id}/keywords")
    def add_rank_keyword(site_id: str, body: RankKeywordBody, request: Request) -> Any:
        keyword = TrackedKeyword(
            keyword_id=uuid.uuid4().hex,
            keyword=body.keyword,
            page_id=body.page_id,
            device=body.device,
            geo=body.geo,
            cadence=body.cadence,
            active=True,
        )
        return _unwrap(_container(request).rank_tracking.add_keyword(
            keyword,
            site_id=site_id,
            organization_id=body.organization_id,
            client_id=body.client_id,
        ))

    @router.post("/rank-tracking/sites/{site_id}/capture")
    def capture_rankings(site_id: str, body: RankCaptureBody, request: Request) -> Any:
        return _unwrap(_container(request).rank_tracking.capture_rankings_now(site_id, body.device, body.geo))

    @router.get("/rank-tracking/sites/{site_id}/report")
    def rank_report(site_id: str, request: Request) -> Any:
        return _unwrap(_container(request).rank_tracking.generate_report(site_id))

    @router.post("/rank-tracking/sites/{site_id}/schedule")
    def schedule_rankings(site_id: str, cadence: str, request: Request) -> Any:
        return {"job_id": _unwrap(_container(request).rank_tracking.schedule_rank_capture(site_id, cadence))}

    @router.post("/reporting/sites/{site_id}/generate")
    def generate_report(site_id: str, body: ReportGenerateBody, request: Request) -> Any:
        definition = ReportDefinition(
            id=uuid.uuid4().hex,
            report_type=body.report_type,
            format=body.format,
            schedule=body.schedule,
            branding_ref=body.branding_ref,
            source_engine_refs=body.source_engine_refs,
            filters=body.filters,
        )
        branding = BrandingConfig(**body.branding)
        return _unwrap(_container(request).reporting.generate_report(
            definition,
            branding,
            site_id=site_id,
            organization_id=body.organization_id,
            client_id=body.client_id,
        ))

    @router.get("/reporting/artifacts/{artifact_id}")
    def get_report_artifact(artifact_id: str, request: Request) -> Any:
        artifact = _unwrap(_container(request).reporting_repo.get_artifact(artifact_id))
        if artifact is None:
            raise HTTPException(status_code=404, detail="Report artifact not found.")
        return artifact

    @router.post("/analytics/sites/{site_id}/analyze")
    def analyze_analytics(site_id: str, request: Request) -> Any:
        return _unwrap(_container(request).analytics.analyze(site_id))

    @router.post("/outreach/sites/{site_id}/analyze")
    def analyze_outreach(site_id: str, request: Request) -> Any:
        c = _container(request)
        report = _unwrap(c.outreach.analyze(site_id))
        return c.outreach_repo.save(c.tenant_id, site_id, report)

    @router.post("/agency/organizations")
    def create_organization(body: OrganizationBody, request: Request) -> Any:
        org = Organization(
            organization_id=body.organization_id or uuid.uuid4().hex,
            name=body.name,
            branding=body.branding,
        )
        return _unwrap(_container(request).agency_management.create_organization(org))

    @router.get("/agency/organizations/{organization_id}")
    def get_organization(organization_id: str, request: Request) -> Any:
        org = _unwrap(_container(request).agency_management.get_organization(organization_id))
        if org is None:
            raise HTTPException(status_code=404, detail="Organization not found.")
        return org

    @router.post("/agency/organizations/{organization_id}/clients")
    def create_client(organization_id: str, body: ClientBody, request: Request) -> Any:
        client = Client(
            client_id=body.client_id or uuid.uuid4().hex,
            organization_id=organization_id,
            name=body.name,
            contact_email=body.contact_email,
        )
        return _unwrap(_container(request).agency_management.create_client(client))

    @router.get("/agency/organizations/{organization_id}/clients")
    def list_clients(organization_id: str, request: Request) -> Any:
        return _unwrap(_container(request).agency_management.list_clients(organization_id))

    @router.post("/agency/organizations/{organization_id}/teams")
    def create_team(organization_id: str, body: TeamBody, request: Request) -> Any:
        team = Team(
            team_id=body.team_id or uuid.uuid4().hex,
            organization_id=organization_id,
            name=body.name,
            members=body.members,
        )
        return _unwrap(_container(request).agency_management.create_team(team))

    @router.get("/agency/organizations/{organization_id}/teams")
    def list_teams(organization_id: str, request: Request) -> Any:
        return _unwrap(_container(request).agency_management.list_teams(organization_id))

    @router.post("/agency/workspaces")
    def save_workspace(body: WorkspaceBody, request: Request) -> Any:
        workspace = Workspace(
            workspace_id=body.workspace_id or uuid.uuid4().hex,
            organization_id=body.organization_id,
            user_id=body.user_id,
            name=body.name,
            client_refs=body.client_refs,
            site_refs=body.site_refs,
            pinned_dashboards=body.pinned_dashboards,
        )
        return _unwrap(_container(request).agency_management.save_workspace(workspace))

    @router.post("/agency/tasks")
    def create_task(body: TaskBody, request: Request) -> Any:
        task = Task(
            task_id=body.task_id or uuid.uuid4().hex,
            organization_id=body.organization_id,
            client_id=body.client_id,
            title=body.title,
            description=body.description,
            referenced_finding_id=body.referenced_finding_id,
            assignee_id=body.assignee_id,
            status=body.status,
        )
        return _unwrap(_container(request).agency_management.create_task(task))

    @router.patch("/agency/tasks/{task_id}/status")
    def update_task_status(task_id: str, body: TaskStatusBody, request: Request) -> Any:
        task = _unwrap(_container(request).agency_management.update_task_status(task_id, body.status))
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found.")
        return task

    @router.post("/agency/notifications")
    def send_notification(body: NotificationBody, request: Request) -> Any:
        notification = Notification(
            notification_id=body.notification_id or uuid.uuid4().hex,
            organization_id=body.organization_id,
            recipient_id=body.recipient_id,
            channel=body.channel,
            message=body.message,
            status=body.status,
        )
        return _unwrap(_container(request).agency_management.send_notification(notification))

    @router.get("/agency/notifications/{recipient_id}")
    def list_notifications(recipient_id: str, request: Request) -> Any:
        return _unwrap(_container(request).agency_management.list_notifications(recipient_id))

    @router.post("/automation/rules")
    def create_automation_rule(rule: AutomationRule, request: Request) -> Any:
        c = _container(request)
        normalized = rule.model_copy(update={"tenant_id": rule.tenant_id or c.tenant_id})
        return _unwrap(c.automation.create_rule(normalized))

    @router.get("/automation/sites/{site_id}/rules")
    def list_automation_rules(site_id: str, request: Request) -> Any:
        c = _container(request)
        return _unwrap(c.automation.get_rules(site_id, tenant_id=c.tenant_id))

    @router.delete("/automation/rules/{rule_id}")
    def disable_automation_rule(rule_id: str, request: Request) -> dict[str, bool]:
        c = _container(request)
        _unwrap(c.automation.disable_rule(rule_id, tenant_id=c.tenant_id))
        return {"disabled": True}

    @router.post("/automation/events")
    def publish_automation_event(event: DomainEvent, request: Request) -> dict[str, Any]:
        c = _container(request)
        normalized = event.model_copy(update={"tenant_id": event.tenant_id or c.tenant_id})
        c.automation.publish_event(normalized)
        return {"published": True, "event_type": normalized.event_type}

    @router.get("/automation/sites/{site_id}/execution-log")
    def automation_logs(site_id: str, request: Request) -> Any:
        c = _container(request)
        return _unwrap(c.automation.get_execution_logs(site_id, tenant_id=c.tenant_id))

    return router
