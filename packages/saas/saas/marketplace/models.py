"""Marketplace DB models and Pydantic schemas for System 7."""

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
    "DeveloperAppRow",
    "AppInstallationRow",
    "OAuthClientRow",
    "DeveloperApp",
    "AppInstallation",
    "OAuthClient",
]


class DeveloperAppRow(SaaSBase):
    """SQLAlchemy Row mapping a registered Developer App."""

    __tablename__ = "saas_marketplace_apps"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    developer_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=True)
    client_id: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    client_secret: Mapped[str] = mapped_column(String, nullable=False)
    redirect_uri: Mapped[str] = mapped_column(String, nullable=False)


class AppInstallationRow(SaaSBase):
    """SQLAlchemy Row mapping installed marketplace apps in tenant workspaces."""

    __tablename__ = "saas_marketplace_installations"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    app_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    installed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    permissions_approved: Mapped[dict] = mapped_column(JSON, nullable=False)  # approved OAuth scopes


class OAuthClientRow(SaaSBase):
    """SQLAlchemy Row mapping OAuth sessions / authorization codes."""

    __tablename__ = "saas_oauth_sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    client_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    auth_code: Mapped[str] = mapped_column(String, nullable=True, unique=True)
    access_token: Mapped[str] = mapped_column(String, nullable=True, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)


# ---- Pydantic schemas ----

class DeveloperApp(BaseModel):
    id: str
    developer_id: str
    name: str
    description: str | None = None
    client_id: str
    client_secret: str
    redirect_uri: str


class AppInstallation(BaseModel):
    id: str
    tenant_id: str
    app_id: str
    installed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    permissions_approved: dict[str, Any] = Field(default_factory=dict)


class OAuthClient(BaseModel):
    id: str
    client_id: str
    auth_code: str | None = None
    access_token: str | None = None
    expires_at: datetime | None = None
