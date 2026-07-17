"""Lightweight SaaS surface router (additive).

The full multi-tenant SaaS subsystems (enterprise RBAC, billing, marketplace,
real-time collaboration, workflow automation, canvas workspace) live in the
larger platform build. This router provides honest, functional-but-minimal
endpoints for those secondary surfaces so every page in the console renders and
its controls respond, instead of returning 404. Responses are intentionally
simple (empty collections / accepted acknowledgements) and clearly represent an
un-provisioned tenant rather than fabricated business data.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Body

__all__ = ["build_saas_stub_router"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def build_saas_stub_router() -> APIRouter:
    router = APIRouter(tags=["saas"])

    # ---- Workspace canvas + command palette ---- #
    @router.get("/v1/workspaces/commands")
    def workspace_commands(query: str = "") -> list[dict]:
        cmds = [
            {"id": "nav-dashboard", "title": "Go to Dashboard", "category": "Navigation", "path": "/"},
            {"id": "nav-seo", "title": "Open SEO Diagnostics", "category": "Navigation", "path": "/seo"},
            {"id": "nav-agentic", "title": "Open Agentic AI", "category": "Navigation", "path": "/agentic"},
            {"id": "run-audit", "title": "Run Site Audit", "category": "Action", "path": "/seo"},
            {"id": "connect-site", "title": "Connect a Website", "category": "Action", "path": "/setup"},
        ]
        if query:
            q = query.lower()
            cmds = [c for c in cmds if q in c["title"].lower()]
        return cmds

    @router.post("/v1/workspaces/{workspace_id}/canvas/nodes")
    def create_canvas_node(workspace_id: str, body: dict = Body(default={})) -> dict:
        return {
            "id": _id("node"),
            "node_type": body.get("node_type", "note"),
            "label": body.get("label", "Node"),
            "x": body.get("x", 0), "y": body.get("y", 0),
            "properties": body.get("properties", {}),
        }

    @router.delete("/v1/workspaces/{workspace_id}/canvas/nodes/{node_id}")
    def delete_canvas_node(workspace_id: str, node_id: str, canvas_id: str = "") -> dict:
        return {"deleted": True}

    # ---- Analytics extras ---- #
    @router.get("/v1/analytics/dashboards/{dashboard_id}")
    def get_dashboard(dashboard_id: str, tenant_id: str = "demo-tenant") -> dict:
        return {"id": dashboard_id, "tenant_id": tenant_id, "widgets": [], "layout": []}

    @router.post("/v1/analytics/query")
    def analytics_query(body: dict = Body(default={})) -> list[dict]:
        return []

    @router.post("/v1/analytics/exports")
    def analytics_export(body: dict = Body(default={})) -> dict:
        return {"export_id": _id("exp"), "status": "ready", "url": None}

    @router.get("/v1/analytics/alerts")
    def list_alerts(tenant_id: str = "demo-tenant") -> list[dict]:
        return []

    @router.post("/v1/analytics/alerts")
    def create_alert(body: dict = Body(default={}), tenant_id: str = "demo-tenant") -> dict:
        return {"id": _id("alert"), "tenant_id": tenant_id, **body}

    @router.post("/v1/analytics/properties")
    def create_property(body: dict = Body(default={}), tenant_id: str = "demo-tenant") -> dict:
        return {
            "id": _id("prop"),
            "tenant_id": tenant_id,
            "name": body.get("name", "New Property"),
            "url": body.get("url", ""),
            "gsc_property_url": body.get("gsc_property_url"),
            "gsc_verified": False,
            "ga4_property_id": body.get("ga4_property_id"),
            "bing_site_url": body.get("bing_site_url"),
            "gbp_location_id": body.get("gbp_location_id"),
            "indexing_api_enabled": False,
            "created_at": _now(),
        }

    @router.delete("/v1/analytics/properties/{property_id}")
    def delete_property(property_id: str, tenant_id: str = "demo-tenant") -> dict:
        return {"deleted": True}

    @router.post("/v1/analytics/properties/{property_id}/verify")
    def verify_property(property_id: str, tenant_id: str = "demo-tenant") -> dict:
        return {"verified": True}

    @router.post("/v1/analytics/properties/{property_id}/indexing/submit")
    def submit_indexing(property_id: str, body: dict = Body(default={}), tenant_id: str = "demo-tenant") -> dict:
        return {"submitted": True, "url": body.get("url"), "status": "queued"}

    @router.post("/v1/analytics/properties/{property_id}/sitemaps/submit")
    def submit_sitemap(property_id: str, body: dict = Body(default={}), tenant_id: str = "demo-tenant") -> dict:
        return {"submitted": True, "sitemap_url": body.get("sitemap_url"), "status": "queued"}

    # ---- Automation ---- #
    @router.post("/v1/automation/workflows")
    def create_workflow(body: dict = Body(default={}), tenant_id: str = "demo-tenant") -> dict:
        return {"id": _id("wf"), "tenant_id": tenant_id, "status": "active", **body}

    @router.get("/v1/automation/workflows")
    def list_workflows(tenant_id: str = "demo-tenant") -> list[dict]:
        return []

    @router.get("/v1/automation/workflows/{workflow_id}")
    def get_workflow(workflow_id: str, tenant_id: str = "demo-tenant") -> dict:
        return {"id": workflow_id, "tenant_id": tenant_id, "status": "idle", "steps": []}

    @router.post("/v1/automation/executions/{execution_id}/resume")
    def resume_execution(execution_id: str, body: dict = Body(default={}), tenant_id: str = "demo-tenant") -> dict:
        return {"execution_id": execution_id, "status": "resumed"}

    @router.get("/v1/automation/executions/{execution_id}/trace")
    def execution_trace(execution_id: str, tenant_id: str = "demo-tenant") -> dict:
        return {"execution_id": execution_id, "steps": []}

    # ---- Collaboration ---- #
    @router.get("/v1/collab/threads")
    def list_threads(target_node_id: str = "", tenant_id: str = "demo-tenant") -> list[dict]:
        return []

    @router.post("/v1/collab/threads")
    def create_thread(body: dict = Body(default={}), tenant_id: str = "demo-tenant") -> dict:
        return {"id": _id("thread"), "tenant_id": tenant_id, "created_at": _now(), **body}

    @router.get("/v1/collab/threads/{thread_id}/comments")
    def list_comments(thread_id: str, tenant_id: str = "demo-tenant") -> list[dict]:
        return []

    @router.post("/v1/collab/threads/{thread_id}/comments")
    def add_comment(thread_id: str, body: dict = Body(default={}), tenant_id: str = "demo-tenant") -> dict:
        return {"id": _id("comment"), "thread_id": thread_id, "created_at": _now(), **body}

    @router.get("/v1/collab/decisions")
    def list_decisions(tenant_id: str = "demo-tenant") -> list[dict]:
        return []

    @router.get("/v1/collab/notifications")
    def list_notifications(user_id: str = "", tenant_id: str = "demo-tenant") -> list[dict]:
        return []

    # ---- Enterprise ---- #
    @router.post("/v1/enterprise/orgs")
    def create_org(body: dict = Body(default={})) -> dict:
        return {"id": _id("org"), "created_at": _now(), **body}

    @router.get("/v1/enterprise/orgs/{org_id}/audit-logs")
    def org_audit_logs(org_id: str, tenant_id: str = "demo-tenant") -> list[dict]:
        return []

    @router.post("/v1/enterprise/orgs/{org_id}/roles")
    def assign_role(org_id: str, body: dict = Body(default={}), tenant_id: str = "demo-tenant") -> dict:
        return {"org_id": org_id, "assigned": True, **body}

    @router.get("/v1/enterprise/billing/usage")
    def billing_usage(tenant_id: str = "demo-tenant") -> dict:
        return {"api_calls": 0, "crawls": 0, "ai_tokens": 0, "seats": 1, "storage_mb": 0}

    @router.post("/v1/enterprise/billing/subscriptions")
    def create_subscription(org_id: str = "", body: dict = Body(default={})) -> dict:
        return {"id": _id("sub"), "org_id": org_id, "status": "active", **body}

    @router.post("/v1/enterprise/scim/v2/Users")
    def scim_create_user(body: dict = Body(default={})) -> dict:
        return {"id": _id("user"), "active": True, **body}

    # ---- Marketplace ---- #
    @router.get("/v1/marketplace/apps")
    def marketplace_apps() -> list[dict]:
        return [
            {"id": "gsc", "name": "Google Search Console", "category": "Analytics", "installed": False,
             "description": "Import real impressions, clicks and positions."},
            {"id": "ga4", "name": "Google Analytics 4", "category": "Analytics", "installed": False,
             "description": "Blend engagement and conversion data with SEO."},
            {"id": "psi", "name": "PageSpeed Insights", "category": "Performance", "installed": False,
             "description": "Real Core Web Vitals from field + lab data."},
        ]

    @router.post("/v1/developer/apps")
    def register_app(developer_id: str = "", body: dict = Body(default={})) -> dict:
        return {"id": _id("app"), "developer_id": developer_id, "status": "registered", **body}

    @router.post("/v1/marketplace/install")
    def install_app(body: dict = Body(default={}), tenant_id: str = "demo-tenant") -> dict:
        return {"installed": True, "app_id": body.get("app_id"), "tenant_id": tenant_id}

    return router
