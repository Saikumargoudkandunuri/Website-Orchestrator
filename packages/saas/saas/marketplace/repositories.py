"""Marketplace Repositories for System 7."""

from __future__ import annotations

from typing import Any
from sqlalchemy import select, delete

from intelligence.repositories._session import SessionMixin
from saas.marketplace.models import (
    DeveloperAppRow,
    AppInstallationRow,
    OAuthClientRow,
    DeveloperApp,
    AppInstallation,
    OAuthClient,
)

__all__ = ["MarketplaceRepository"]


class MarketplaceRepository(SessionMixin):
    """SaaS Marketplace Repository managing developer apps and installations."""

    def save_app(self, app: DeveloperApp) -> None:
        with self._session() as session:
            existing = session.get(DeveloperAppRow, app.id)
            if existing:
                existing.name = app.name
                existing.description = app.description
                existing.redirect_uri = app.redirect_uri
            else:
                session.add(DeveloperAppRow(
                    id=app.id,
                    developer_id=app.developer_id,
                    name=app.name,
                    description=app.description,
                    client_id=app.client_id,
                    client_secret=app.client_secret,
                    redirect_uri=app.redirect_uri,
                ))
            session.commit()

    def get_app(self, app_id: str) -> DeveloperApp | None:
        with self._session() as session:
            row = session.get(DeveloperAppRow, app_id)
            if row:
                return DeveloperApp(
                    id=row.id,
                    developer_id=row.developer_id,
                    name=row.name,
                    description=row.description,
                    client_id=row.client_id,
                    client_secret=row.client_secret,
                    redirect_uri=row.redirect_uri,
                )
            return None

    def list_apps(self) -> list[DeveloperApp]:
        with self._session() as session:
            rows = session.execute(select(DeveloperAppRow)).scalars().all()
            return [
                DeveloperApp(
                    id=r.id,
                    developer_id=r.developer_id,
                    name=r.name,
                    description=r.description,
                    client_id=r.client_id,
                    client_secret=r.client_secret,
                    redirect_uri=r.redirect_uri,
                )
                for r in rows
            ]

    def save_installation(self, inst: AppInstallation) -> None:
        tenant = self._resolve_tenant(inst.tenant_id)
        with self._session() as session:
            existing = session.execute(
                select(AppInstallationRow).where(
                    AppInstallationRow.tenant_id == tenant,
                    AppInstallationRow.app_id == inst.app_id,
                )
            ).scalar_one_or_none()

            if existing:
                existing.permissions_approved = inst.permissions_approved
            else:
                session.add(AppInstallationRow(
                    id=inst.id,
                    tenant_id=tenant,
                    app_id=inst.app_id,
                    installed_at=inst.installed_at,
                    permissions_approved=inst.permissions_approved,
                ))
            session.commit()

    def get_installation(self, tenant_id: str, app_id: str) -> AppInstallation | None:
        tenant = self._resolve_tenant(tenant_id)
        with self._session() as session:
            row = session.execute(
                select(AppInstallationRow).where(
                    AppInstallationRow.tenant_id == tenant,
                    AppInstallationRow.app_id == app_id,
                )
            ).scalar_one_or_none()
            if row:
                return AppInstallation(
                    id=row.id,
                    tenant_id=row.tenant_id,
                    app_id=row.app_id,
                    installed_at=row.installed_at,
                    permissions_approved=row.permissions_approved,
                )
            return None

    def list_installations(self, tenant_id: str) -> list[AppInstallation]:
        tenant = self._resolve_tenant(tenant_id)
        with self._session() as session:
            rows = session.execute(
                select(AppInstallationRow).where(AppInstallationRow.tenant_id == tenant)
            ).scalars().all()
            return [
                AppInstallation(
                    id=r.id,
                    tenant_id=r.tenant_id,
                    app_id=r.app_id,
                    installed_at=r.installed_at,
                    permissions_approved=r.permissions_approved,
                )
                for r in rows
            ]
