"""Enterprise SaaS DB models and Pydantic schemas for System 2."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from pydantic import BaseModel, Field
from sqlalchemy import Boolean, DateTime, Float, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

try:
    from sqlalchemy import JSON
except ImportError:
    from sqlalchemy import Text as JSON

from saas.db import SaaSBase

__all__ = [
    "OrganizationRow",
    "BusinessUnitRow",
    "TeamRow",
    "UserRoleAssignmentRow",
    "AuditTrailRecordRow",
    "SubscriptionRow",
    "FeatureFlagRow",
    "ApiKeyRow",
    "Organization",
    "BusinessUnit",
    "Team",
    "UserRoleAssignment",
    "AuditTrailRecord",
    "Subscription",
    "FeatureFlag",
    "ApiKey",
]


class OrganizationRow(SaaSBase):
    """SQLAlchemy Row mapping an enterprise Organization."""

    __tablename__ = "saas_organizations"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    billing_email: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class BusinessUnitRow(SaaSBase):
    """SQLAlchemy Row mapping a Business Unit inside an Org."""

    __tablename__ = "saas_business_units"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    org_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)


class TeamRow(SaaSBase):
    """SQLAlchemy Row mapping logical user groupings (Teams)."""

    __tablename__ = "saas_teams"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    org_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)


class UserRoleAssignmentRow(SaaSBase):
    """SQLAlchemy Row mapping users to roles (RBAC)."""

    __tablename__ = "saas_user_roles"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    role: Mapped[str] = mapped_column(String, nullable=False)  # "admin", "writer", "reader"


class AuditTrailRecordRow(SaaSBase):
    """SQLAlchemy Row mapping immutable signed audit logs."""

    __tablename__ = "saas_audit_trail"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    actor: Mapped[str] = mapped_column(String, nullable=False)
    action: Mapped[str] = mapped_column(String, nullable=False)
    target_id: Mapped[str] = mapped_column(String, nullable=False)
    changes_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    signature: Mapped[str] = mapped_column(String, nullable=False)  # cryptographic HMAC
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SubscriptionRow(SaaSBase):
    """SQLAlchemy Row mapping Stripe subscription state."""

    __tablename__ = "saas_subscriptions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    org_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    stripe_sub_id: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    plan_tier: Mapped[str] = mapped_column(String, nullable=False)  # "free", "growth", "enterprise"
    status: Mapped[str] = mapped_column(String, nullable=False)  # "active", "canceled"
    current_period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class FeatureFlagRow(SaaSBase):
    """SQLAlchemy Row mapping feature flags per scope."""

    __tablename__ = "saas_feature_flags"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    flag_key: Mapped[str] = mapped_column(String, nullable=False, index=True)
    scope: Mapped[str] = mapped_column(String, nullable=False)  # "global", "org", "user"
    scope_id: Mapped[str] = mapped_column(String, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class ApiKeyRow(SaaSBase):
    """SQLAlchemy Row mapping active API keys."""

    __tablename__ = "saas_api_keys"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    org_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    key_hash: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


# ---- Pydantic schemas ----

class Organization(BaseModel):
    id: str
    name: str
    billing_email: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class BusinessUnit(BaseModel):
    id: str
    org_id: str
    name: str


class Team(BaseModel):
    id: str
    org_id: str
    name: str


class UserRoleAssignment(BaseModel):
    id: str
    tenant_id: str
    user_id: str
    role: str


class AuditTrailRecord(BaseModel):
    id: str
    tenant_id: str
    actor: str
    action: str
    target_id: str
    changes_json: dict[str, Any] = Field(default_factory=dict)
    signature: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Subscription(BaseModel):
    id: str
    org_id: str
    stripe_sub_id: str
    plan_tier: str
    status: str
    current_period_end: datetime


class FeatureFlag(BaseModel):
    id: str
    flag_key: str
    scope: str
    scope_id: str
    is_enabled: bool = False


class ApiKey(BaseModel):
    id: str
    org_id: str
    key_hash: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
