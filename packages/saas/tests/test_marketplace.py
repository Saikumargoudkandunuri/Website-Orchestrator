"""Unit tests for System 7 Marketplace & Ecosystem."""

from __future__ import annotations

import pytest

from saas.marketplace.models import DeveloperApp, AppInstallation
from saas.marketplace.repositories import MarketplaceRepository
from saas.marketplace.services import AppRegistryService, AppInstallationService, OAuthServerService


class TestMarketplaceSystem:
    def test_register_and_list_apps(self, db_session_factory):
        repo = MarketplaceRepository(db_session_factory, tenant_id="t1")
        service = AppRegistryService(repo)

        app = service.register_app("dev-123", "Search Booster", "https://redirect.com")
        assert app.name == "Search Booster"
        assert len(app.client_id) > 10

        apps = repo.list_apps()
        assert len(apps) == 1
        assert apps[0].id == app.id

    def test_tenant_app_installations(self, db_session_factory):
        repo = MarketplaceRepository(db_session_factory, tenant_id="t1")
        registry = AppRegistryService(repo)
        installer = AppInstallationService(repo)

        app = registry.register_app("dev-123", "Keyword Tracker", "https://redirect.com")
        
        # Install in t1 workspace
        inst = installer.install_app("t1", app.id, ["read", "write"])
        assert inst.app_id == app.id

        # Verify list of installations
        inst_list = repo.list_installations("t1")
        assert len(inst_list) == 1
        assert inst_list[0].permissions_approved["scopes"] == ["read", "write"]

        # Tenant isolation
        assert len(repo.list_installations("t2")) == 0

    def test_oauth_pkce_exchange_flow(self):
        service = OAuthServerService()

        # Phase 1: Get authorization code
        code = service.generate_auth_code("client-99", "pkce-challenge-xyz")
        assert len(code) > 10

        # Phase 2: Exchange with valid verifier
        token = service.exchange_code_for_token(code, "pkce-challenge-xyz")
        assert token is not None
        assert token.startswith("token_")

        # Phase 3: Re-use of code fails
        token_retry = service.exchange_code_for_token(code, "pkce-challenge-xyz")
        assert token_retry is None
