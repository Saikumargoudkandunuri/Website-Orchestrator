"""Automation DB models and Pydantic schemas for System 4."""

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
    "WorkflowDefinitionRow",
    "WorkflowConnectionRow",
    "WorkflowExecutionRow",
    "WorkflowSuspensionRow",
    "WebhookEndpointRow",
    "WorkflowDefinition",
    "WorkflowConnection",
    "WorkflowExecution",
    "WorkflowSuspension",
    "WebhookEndpoint",
]


class WorkflowDefinitionRow(SaaSBase):
    """SQLAlchemy Row mapping a visual Workflow DAG definition."""

    __tablename__ = "saas_workflow_definitions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    trigger_type: Mapped[str] = mapped_column(String, nullable=False)  # "event", "schedule"
    nodes_json: Mapped[dict] = mapped_column(JSON, nullable=False)  # visual graph nodes
    edges_json: Mapped[dict] = mapped_column(JSON, nullable=False)  # visual connections


class WorkflowConnectionRow(SaaSBase):
    """SQLAlchemy Row mapping credentials to external services."""

    __tablename__ = "saas_workflow_connections"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    service_name: Mapped[str] = mapped_column(String, nullable=False)  # "slack", "wp"
    credentials_json: Mapped[dict] = mapped_column(JSON, nullable=False)  # encrypted API keys


class WorkflowExecutionRow(SaaSBase):
    """SQLAlchemy Row mapping workflow run instances and history."""

    __tablename__ = "saas_workflow_executions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    workflow_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String, nullable=False)  # "running", "paused", "completed", "failed"
    current_node_id: Mapped[str] = mapped_column(String, nullable=True)
    logs_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class WorkflowSuspensionRow(SaaSBase):
    """SQLAlchemy Row mapping paused runs awaiting developer approval."""

    __tablename__ = "saas_workflow_suspensions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    execution_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    node_id: Mapped[str] = mapped_column(String, nullable=False)
    reason: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class WebhookEndpointRow(SaaSBase):
    """SQLAlchemy Row mapping webhook subscriptions."""

    __tablename__ = "saas_webhook_endpoints"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    target_url: Mapped[str] = mapped_column(String, nullable=False)
    secret_token: Mapped[str] = mapped_column(String, nullable=False)  # HMAC verify token


# ---- Pydantic schemas ----

class WorkflowDefinition(BaseModel):
    id: str
    tenant_id: str
    name: str
    trigger_type: str
    nodes_json: dict[str, Any] = Field(default_factory=dict)
    edges_json: dict[str, Any] = Field(default_factory=dict)


class WorkflowConnection(BaseModel):
    id: str
    tenant_id: str
    service_name: str
    credentials_json: dict[str, Any] = Field(default_factory=dict)


class WorkflowExecution(BaseModel):
    id: str
    tenant_id: str
    workflow_id: str
    status: str
    current_node_id: str | None = None
    logs_json: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class WorkflowSuspension(BaseModel):
    id: str
    tenant_id: str
    execution_id: str
    node_id: str
    reason: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class WebhookEndpoint(BaseModel):
    id: str
    tenant_id: str
    target_url: str
    secret_token: str
