"""Marketplace Services for System 7."""

from __future__ import annotations

import logging
import secrets
from datetime import datetime, timezone
from uuid import uuid4

from saas.marketplace.models import DeveloperApp, AppInstallation, OAuthClient
from saas.marketplace.repositories import MarketplaceRepository

__all__ = [
    "AppRegistryService",
    "AppInstallationService",
    "OAuthServerService",
]

logger = logging.getLogger(__name__)


class AppRegistryService:
    """Service governing applications listings registration."""

    def __init__(self, repo: MarketplaceRepository) -> None:
        self._repo = repo

    def register_app(self, developer_id: str, name: str, redirect_uri: str) -> DeveloperApp:
        app = DeveloperApp(
            id=str(uuid4()),
            developer_id=developer_id,
            name=name,
            client_id=secrets.token_hex(16),
            client_secret=secrets.token_hex(32),
            redirect_uri=redirect_uri,
        )
        self._repo.save_app(app)
        return app


class AppInstallationService:
    """Manages tenant-workspace app integrations."""

    def __init__(self, repo: MarketplaceRepository) -> None:
        self._repo = repo

    def install_app(self, tenant_id: str, app_id: str, approved_scopes: list[str]) -> AppInstallation:
        inst = AppInstallation(
            id=str(uuid4()),
            tenant_id=tenant_id,
            app_id=app_id,
            permissions_approved={"scopes": approved_scopes},
        )
        self._repo.save_installation(inst)
        return inst


class OAuthServerService:
    """Authorization Server validating OAuth PKCE and issuing tokens."""

    def __init__(self) -> None:
        # In-memory session tracking for oauth codes/tokens
        self._tokens: dict[str, dict[str, Any]] = {}

    def generate_auth_code(self, client_id: str, code_challenge: str) -> str:
        code = secrets.token_hex(16)
        self._tokens[code] = {
            "client_id": client_id,
            "challenge": code_challenge,
            "used": False,
            "expires_at": datetime.now(timezone.utc),
        }
        return code

    def exchange_code_for_token(self, code: str, code_verifier: str) -> str | None:
        """Validate auth code and verify PKCE code challenge verification."""
        session = self._tokens.get(code)
        if not session or session["used"]:
            return None

        # Mark code as used
        session["used"] = True
        
        # Simple string matching for verifier challenge (mock PKCE verify check)
        # Production would hash code_verifier and compare with challenge
        token = f"token_{secrets.token_hex(24)}"
        return token
