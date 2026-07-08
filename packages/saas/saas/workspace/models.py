"""Workspace DB models and schemas for System 1."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from pydantic import BaseModel, Field
from sqlalchemy import DateTime, Float, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

try:
    from sqlalchemy import JSON
except ImportError:
    from sqlalchemy import Text as JSON

from saas.db import SaaSBase

__all__ = [
    "WorkspaceRow",
    "CanvasRow",
    "CanvasNodeRow",
    "WorkspaceAnnotationRow",
    "Workspace",
    "Canvas",
    "CanvasNode",
    "WorkspaceAnnotation",
]


class WorkspaceRow(SaaSBase):
    """SQLAlchemy Row mapping a tenant Workspace."""

    __tablename__ = "saas_workspaces"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CanvasRow(SaaSBase):
    """SQLAlchemy Row mapping a Canvas spatial view."""

    __tablename__ = "saas_canvases"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    workspace_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CanvasNodeRow(SaaSBase):
    """SQLAlchemy Row mapping an element inside a Canvas."""

    __tablename__ = "saas_canvas_nodes"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    canvas_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    node_type: Mapped[str] = mapped_column(String, nullable=False)
    label: Mapped[str] = mapped_column(String, nullable=False)
    x: Mapped[float] = mapped_column(Float, nullable=False)
    y: Mapped[float] = mapped_column(Float, nullable=False)
    width: Mapped[float] = mapped_column(Float, nullable=False, default=100.0)
    height: Mapped[float] = mapped_column(Float, nullable=False, default=100.0)
    metadata_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class WorkspaceAnnotationRow(SaaSBase):
    """SQLAlchemy Row mapping comments/pins linked to elements or coordinates."""

    __tablename__ = "saas_workspace_annotations"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    workspace_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    target_id: Mapped[str] = mapped_column(String, nullable=True)  # link to node or specific element
    author: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


# ---- Pydantic schemas ----

class Workspace(BaseModel):
    id: str
    tenant_id: str
    name: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Canvas(BaseModel):
    id: str
    tenant_id: str
    workspace_id: str
    name: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CanvasNode(BaseModel):
    id: str
    tenant_id: str
    canvas_id: str
    node_type: str
    label: str
    x: float
    y: float
    width: float = 100.0
    height: float = 100.0
    metadata_payload: dict[str, Any] = Field(default_factory=dict)


class WorkspaceAnnotation(BaseModel):
    id: str
    tenant_id: str
    workspace_id: str
    target_id: str | None = None
    author: str
    content: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
