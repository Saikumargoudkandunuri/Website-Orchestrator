"""FastAPI Router endpoints for System 7 Marketplace & Ecosystem."""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from saas.marketplace.models import DeveloperApp, AppInstallation
from saas.marketplace.services import AppRegistryService, AppInstallationService, OAuthServerService

__all__ = ["build_marketplace_router"]


class AppRegisterRequest(BaseModel):
    name: str
    redirect_uri: str


class InstallRequest(BaseModel):
    app_id: str
    scopes: list[str] = []


class AuthCodeRequest(BaseModel):
    client_id: str
    code_challenge: str


class TokenExchangeRequest(BaseModel):
    code: str
    code_verifier: str


def build_marketplace_router(
    registry: AppRegistryService,
    installer: AppInstallationService,
    oauth: OAuthServerService,
) -> APIRouter:
    router = APIRouter(prefix="/v1", tags=["Marketplace Ecosystem"])

    @router.get("/marketplace/apps", response_model=list[DeveloperApp])
    def get_apps() -> list[DeveloperApp]:
        return registry._repo.list_apps()

    @router.post("/developer/apps", response_model=DeveloperApp)
    def register_dev_app(req: AppRegisterRequest, developer_id: str) -> DeveloperApp:
        return registry.register_app(developer_id, req.name, req.redirect_uri)

    @router.post("/marketplace/install", response_model=AppInstallation)
    def install_marketplace_app(req: InstallRequest, tenant_id: str) -> AppInstallation:
        app = registry._repo.get_app(req.app_id)
        if not app:
            raise HTTPException(status_code=404, detail="App not found in directory")
        return installer.install_app(tenant_id, req.app_id, req.scopes)

    @router.post("/oauth/authorize")
    def oauth_authorize(req: AuthCodeRequest) -> dict[str, str]:
        code = oauth.generate_auth_code(req.client_id, req.code_challenge)
        return {"code": code}

    @router.post("/oauth/token")
    def oauth_token(req: TokenExchangeRequest) -> dict[str, str]:
        token = oauth.exchange_code_for_token(req.code, req.code_verifier)
        if not token:
            raise HTTPException(status_code=400, detail="Invalid authorization code or PKCE challenge verification failed")
        return {"access_token": token, "token_type": "bearer"}

    return router
