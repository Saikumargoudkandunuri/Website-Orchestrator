"""FastAPI Router endpoints for System 2 Enterprise SaaS Platform."""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from saas.enterprise.models import Organization, Subscription, AuditTrailRecord, UserRoleAssignment
from saas.enterprise.services import AccessControlService, UsageMeterService, AuditLogService, StripeService

__all__ = ["build_enterprise_router"]


class OrgCreateRequest(BaseModel):
    name: str
    billing_email: str


class RoleRequest(BaseModel):
    user_id: str
    role: str


class SubscriptionRequest(BaseModel):
    plan_tier: str


class ScimUserRequest(BaseModel):
    userName: str
    emails: list[dict[str, Any]]
    active: bool = True


def build_enterprise_router(
    rbac: AccessControlService,
    meter: UsageMeterService,
    audit: AuditLogService,
    stripe: StripeService,
) -> APIRouter:
    router = APIRouter(prefix="/v1/enterprise", tags=["Enterprise Platform"])

    @router.post("/orgs", response_model=Organization)
    def create_org(req: OrgCreateRequest) -> Organization:
        # Returns organization metadata
        from uuid import uuid4
        from datetime import datetime, timezone
        return Organization(
            id=str(uuid4()),
            name=req.name,
            billing_email=req.billing_email,
            created_at=datetime.now(timezone.utc),
        )

    @router.get("/orgs/{id}/audit-logs", response_model=list[AuditTrailRecord])
    def get_audit_logs(id: str, tenant_id: str) -> list[AuditTrailRecord]:
        return audit._repo.list_audits(tenant_id)

    @router.post("/orgs/{id}/roles")
    def assign_user_role(id: str, req: RoleRequest, tenant_id: str) -> dict[str, bool]:
        from uuid import uuid4
        assignment = UserRoleAssignment(
            id=str(uuid4()),
            tenant_id=tenant_id,
            user_id=req.user_id,
            role=req.role,
        )
        rbac._repo.save_role(assignment)
        return {"success": True}

    @router.post("/scim/v2/Users")
    def scim_create_user(req: ScimUserRequest) -> dict[str, Any]:
        # Minimal compliant RFC SCIM return payload
        from uuid import uuid4
        user_id = str(uuid4())
        return {
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
            "id": user_id,
            "userName": req.userName,
            "emails": req.emails,
            "active": req.active,
        }

    @router.post("/billing/subscriptions", response_model=Subscription)
    def create_subscription(req: SubscriptionRequest, org_id: str) -> Subscription:
        return stripe.create_mock_subscription(org_id, req.plan_tier)

    @router.get("/billing/usage")
    def get_usage(tenant_id: str) -> dict[str, int]:
        return {"usage": meter.get_usage(tenant_id)}

    return router
