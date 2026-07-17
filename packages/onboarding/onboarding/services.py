"""Onboarding services — the orchestration layer.

These services implement the Foundation sub-project's business logic and wire
the detector, integration discovery, initial crawler, and digital-twin builder
to the existing subsystems (Crawler, Digital_Twin, Publishing_Adapter, Editing)
and the OnboardingRepository.

Services:
* :class:`WorkspaceService`
* :class:`ProjectService`
* :class:`WebsiteService`
* :class:`ConnectionService` (verify/reconnect/disconnect + capability detection)
* :class:`OnboardingOrchestrator` (high-level onboarding flow)

All persistence is tenant-scoped. The services never duplicate subsystem logic;
they integrate it.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from core.exceptions import OrchestratorError
from core.interfaces import CrawlerPort, DigitalTwinPort, PublishingAdapterPort
from pydantic import SecretStr

from onboarding.detector import DetectionResult, WebsiteDetector
from onboarding.encryption import decrypt_secret, encrypt_secret
from onboarding.integrations import IntegrationDiscoveryService
from onboarding.models import Integration
from onboarding.repository import OnboardingRepository
from onboarding.state_machine import OnboardingStateMachine

__all__ = [
    "WorkspaceService",
    "ProjectService",
    "WebsiteService",
    "ConnectionService",
    "OnboardingOrchestrator",
    "OnboardingError",
]

#: Capabilities detected for a verified connection (architecture review:
#: Capabilities). Stored as JSON on the Connection row.
_DETECTED_CAPABILITIES: list[str] = [
    "crawl",
    "read",
    "draft",
    "publish",
    "delete",
    "rollback",
    "plugin_install",
    "theme_modify",
    "media_upload",
    "database_backup",
]


class OnboardingError(OrchestratorError):
    """Base error for onboarding service failures (mapped to 4xx/5xx)."""


# --- Workspace ----------------------------------------------------------------


class WorkspaceService:
    """Create/rename/delete/load/switch/list workspaces."""

    def __init__(self, repo: OnboardingRepository) -> None:
        self._repo = repo

    def create(self, tenant_id: str, *, name: str, description: str | None = None) -> dict:
        row = self._repo.create_workspace(tenant_id, name=name, description=description)
        return _row_to_dict(row)

    def get(self, tenant_id: str, workspace_id: str) -> dict | None:
        row = self._repo.get_workspace(tenant_id, workspace_id)
        return _row_to_dict(row) if row else None

    def list(self, tenant_id: str) -> list[dict]:
        return [_row_to_dict(r) for r in self._repo.list_workspaces(tenant_id)]

    def update(self, tenant_id: str, workspace_id: str, **changes: Any) -> dict | None:
        row = self._repo.update_workspace(tenant_id, workspace_id, **changes)
        return _row_to_dict(row) if row else None

    def delete(self, tenant_id: str, workspace_id: str) -> bool:
        return self._repo.delete_workspace(tenant_id, workspace_id)


# --- Project ------------------------------------------------------------------


class ProjectService:
    """Create/rename/delete/move/archive/list projects."""

    def __init__(self, repo: OnboardingRepository) -> None:
        self._repo = repo

    def create(
        self, tenant_id: str, *, workspace_id: str, name: str, description: str | None = None
    ) -> dict:
        row = self._repo.create_project(
            tenant_id, workspace_id=workspace_id, name=name, description=description
        )
        return _row_to_dict(row)

    def get(self, tenant_id: str, project_id: str) -> dict | None:
        row = self._repo.get_project(tenant_id, project_id)
        return _row_to_dict(row) if row else None

    def list(self, tenant_id: str, workspace_id: str | None = None) -> list[dict]:
        return [
            _row_to_dict(r) for r in self._repo.list_projects(tenant_id, workspace_id)
        ]

    def update(self, tenant_id: str, project_id: str, **changes: Any) -> dict | None:
        row = self._repo.update_project(tenant_id, project_id, **changes)
        return _row_to_dict(row) if row else None

    def delete(self, tenant_id: str, project_id: str) -> bool:
        return self._repo.delete_project(tenant_id, project_id)


# --- Website ------------------------------------------------------------------


class WebsiteService:
    """Create/edit/delete/load websites and toggle AI/automation/memory.

    Product constraint (Milestone 5): one account = one connected website.
    ``tenant_id``/``website_id`` remain the internal multi-tenant/multi-site
    persistence keys — required for governance, audit, rollback, and CMO
    memory scoping — but the product surface never lets a tenant provision a
    second website. :meth:`create` enforces that at the single choke point
    every onboarding path (API route, orchestrator, future admin tooling) goes
    through, so the one-website invariant can never be silently bypassed.
    """

    def __init__(self, repo: OnboardingRepository) -> None:
        self._repo = repo

    def create(
        self,
        tenant_id: str,
        *,
        workspace_id: str,
        project_id: str,
        group_id: str | None,
        name: str,
        url: str,
        display_name: str | None,
        environment: str,
        website_type: str,
    ) -> dict:
        existing = self._repo.list_websites(tenant_id)
        if existing:
            raise OnboardingError(
                "This account already has a connected website. Each account "
                "supports exactly one connected website; disconnect the "
                "existing website before connecting a different one."
            )
        row = self._repo.create_website(
            tenant_id,
            workspace_id=workspace_id,
            project_id=project_id,
            group_id=group_id,
            name=name,
            url=url,
            display_name=display_name,
            environment=environment,
            website_type=website_type,
        )
        return _row_to_dict(row)

    def get_my_website(self, tenant_id: str) -> dict | None:
        """Return the account's single connected website, or ``None`` before
        onboarding has connected one (Milestone 5 — single-website product
        surface). Auto-loaded on every login; there is never a website list or
        switcher exposed to the user."""
        existing = self._repo.list_websites(tenant_id)
        return _row_to_dict(existing[0]) if existing else None

    def get(self, tenant_id: str, website_id: str) -> dict | None:
        row = self._repo.get_website(tenant_id, website_id)
        return _row_to_dict(row) if row else None

    def list(
        self,
        tenant_id: str,
        *,
        workspace_id: str | None = None,
        project_id: str | None = None,
        group_id: str | None = None,
    ) -> list[dict]:
        return [
            _row_to_dict(r)
            for r in self._repo.list_websites(
                tenant_id,
                workspace_id=workspace_id,
                project_id=project_id,
                group_id=group_id,
            )
        ]

    def update(self, tenant_id: str, website_id: str, **changes: Any) -> dict | None:
        # Agent-slot settings share one JSON column with versioned CMO memory.
        # Merge instead of replacing so an ordinary settings save cannot erase
        # executive memory or its schedule.
        incoming = changes.get("agent_config")
        if isinstance(incoming, dict):
            existing = self._repo.get_website(tenant_id, website_id)
            if existing is None:
                return None
            merged = dict(existing.agent_config or {})
            merged.update(incoming)
            changes["agent_config"] = merged
        row = self._repo.update_website(tenant_id, website_id, **changes)
        return _row_to_dict(row) if row else None

    def delete(self, tenant_id: str, website_id: str) -> bool:
        return self._repo.delete_website(tenant_id, website_id)

    def set_feature_flags(
        self,
        tenant_id: str,
        website_id: str,
        *,
        ai_enabled: bool | None = None,
        automation_enabled: bool | None = None,
        memory_enabled: bool | None = None,
        approval_mode: str | None = None,
    ) -> dict | None:
        changes: dict[str, Any] = {}
        if ai_enabled is not None:
            changes["ai_enabled"] = ai_enabled
        if automation_enabled is not None:
            changes["automation_enabled"] = automation_enabled
        if memory_enabled is not None:
            changes["memory_enabled"] = memory_enabled
        if approval_mode is not None:
            changes["approval_mode"] = approval_mode
        return self.update(tenant_id, website_id, **changes)


# --- Connection ---------------------------------------------------------------


class ConnectionService:
    """Create/verify/reconnect/disconnect connections + detect capabilities."""

    def __init__(
        self,
        repo: OnboardingRepository,
        *,
        publishing_adapter: PublishingAdapterPort | None = None,
        detector: WebsiteDetector | None = None,
    ) -> None:
        self._repo = repo
        self._publishing = publishing_adapter
        self._detector = detector or WebsiteDetector()

    def create(
        self,
        tenant_id: str,
        *,
        website_id: str,
        connection_type: str,
        credential: str | SecretStr | None,
        connection_meta: dict | None = None,
    ) -> dict:
        encrypted = encrypt_secret(credential)
        row = self._repo.create_connection(
            tenant_id,
            website_id=website_id,
            connection_type=connection_type,
            encrypted_credentials=encrypted,
            connection_meta=connection_meta,
            capabilities=None,
        )
        return _row_to_dict(row)

    def verify(
        self,
        tenant_id: str,
        *,
        website_id: str,
        connection_type: str,
        credential: str | SecretStr | None,
        connection_meta: dict | None = None,
    ) -> dict:
        """Verify a connection, detect capabilities, and persist the result.

        Returns a dict with ``status``, ``capabilities``, ``warnings``, and
        ``error``. On success the connection is created/updated and marked
        verified; on failure the error is recorded (no exception leaks the
        credential).
        """
        warnings: list[str] = []
        try:
            if self._publishing is None or connection_type in ("read_only", "demo"):
                # No live adapter (e.g. demo/read-only): accept the connection
                # structurally and record a warning rather than failing.
                if connection_type in ("read_only", "demo"):
                    warnings.append("Read-only/demo connection accepted in offline mode; no write access.")
                elif self._publishing is None:
                    warnings.append("No live publishing adapter configured; connection accepted in offline mode.")
                capabilities = {cap: False for cap in _DETECTED_CAPABILITIES}
                capabilities["read"] = True
                capabilities["crawl"] = True
            else:
                # Exercise the adapter to confirm credentials work. A real
                # WordPressClient raises typed PublishingError subclasses on
                # auth/transport failure; we catch and record them safely.
                self._publishing.list_pages()
                capabilities = {cap: True for cap in _DETECTED_CAPABILITIES}
        except Exception as exc:  # noqa: BLE001 - never leak credential detail
            error = f"{type(exc).__name__}"
            conn = self._repo.create_connection(
                tenant_id,
                website_id=website_id,
                connection_type=connection_type,
                encrypted_credentials=encrypt_secret(credential),
                connection_meta=connection_meta,
                capabilities=None,
            )
            self._repo.update_connection(
                tenant_id, conn.id, is_active=False, last_error=error
            )
            return {
                "website_id": website_id,
                "connection_type": connection_type,
                "status": "ERROR",
                "capabilities": None,
                "warnings": warnings,
                "error": error,
            }

        encrypted = encrypt_secret(credential)
        conn = self._repo.create_connection(
            tenant_id,
            website_id=website_id,
            connection_type=connection_type,
            encrypted_credentials=encrypted,
            connection_meta=connection_meta,
            capabilities=capabilities,
        )
        self._repo.update_connection(
            tenant_id, conn.id, is_active=True, verified_at=datetime.now(timezone.utc)
        )
        return {
            "website_id": website_id,
            "connection_type": connection_type,
            "status": "CONNECTED",
            "capabilities": capabilities,
            "warnings": warnings,
            "error": None,
        }

    def reconnect(self, tenant_id: str, connection_id: str) -> dict:
        row = self._repo.get_connection(tenant_id, connection_id)
        if row is None:
            raise OnboardingError(f"Connection {connection_id} not found")
        # Re-verify using stored (decrypted) credentials.
        secret = decrypt_secret(row.encrypted_credentials)
        return self.verify(
            tenant_id,
            website_id=row.website_id,
            connection_type=row.connection_type,
            credential=secret,
            connection_meta=row.connection_meta,
        )

    def disconnect(self, tenant_id: str, connection_id: str) -> bool:
        row = self._repo.get_connection(tenant_id, connection_id)
        if row is None:
            return False
        self._repo.update_connection(tenant_id, connection_id, is_active=False)
        return True

    def list(self, tenant_id: str, website_id: str) -> list[dict]:
        return [_row_to_dict(r) for r in self._repo.list_connections(tenant_id, website_id)]


# --- Orchestrator -------------------------------------------------------------


class OnboardingOrchestrator:
    """High-level onboarding flow tying detection, integrations, crawl, twin."""

    def __init__(
        self,
        repo: OnboardingRepository,
        *,
        crawler: CrawlerPort,
        digital_twin: DigitalTwinPort,
        check_engine: Any,
        fix_generator: Any,
        detector: WebsiteDetector | None = None,
        integration_discovery: IntegrationDiscoveryService | None = None,
        publishing_adapter: PublishingAdapterPort | None = None,
        tenant_id: str,
    ) -> None:
        self._repo = repo
        self._crawler = crawler
        self._digital_twin = digital_twin
        self._check_engine = check_engine
        self._fix_generator = fix_generator
        self._detector = detector or WebsiteDetector()
        self._integrations = integration_discovery or IntegrationDiscoveryService()
        # Milestone 4 — resolves the stable URL <-> WordPress page/post mapping
        # right after a crawl, from the real live listing. Optional so existing
        # callers/tests that inject no adapter (read-only/demo/offline mode)
        # keep working unchanged; the mapping step is then simply skipped.
        self._publishing_adapter = publishing_adapter
        self._tenant_id = tenant_id
        # Cache of the most recent crawl's pages, keyed by website_id, so the
        # digital-twin build can consume them without re-crawling. The
        # Digital_Twin repository persists pages but does not expose a list-all
        # read, so we keep the in-memory copy here (the source of truth for the
        # twin build is the crawl output, which is also persisted).
        self._crawled_pages: dict[str, list[Any]] = {}

    def detect_website(self, website_id: str) -> DetectionResult:
        """Run detection and persist the result onto the Website row."""
        row = self._repo.get_website(self._tenant_id, website_id)
        if row is None:
            raise OnboardingError(f"Website {website_id} not found")
        self._repo.update_website(
            self._tenant_id, website_id, onboarding_state="detecting"
        )
        result = self._detector.detect(row.url)
        self._repo.update_website(
            self._tenant_id,
            website_id,
            onboarding_state=OnboardingStateMachine.transition("detecting", "discovering"),
            **result.to_website_fields(),
        )
        return result

    def discover_integrations(self, website_id: str) -> list[dict]:
        """Discover integrations and persist them as Integration rows."""
        row = self._repo.get_website(self._tenant_id, website_id)
        if row is None:
            raise OnboardingError(f"Website {website_id} not found")
        discovered = self._integrations.discover(row.url)
        created: list[Integration] = []
        for item in discovered:
            created.append(
                self._repo.create_integration(
                    self._tenant_id,
                    website_id=website_id,
                    provider=item.provider,
                    status=item.status,
                    metadata=item.metadata,
                )
            )
        self._repo.update_website(
            self._tenant_id,
            website_id,
            onboarding_state=OnboardingStateMachine.transition("discovering", "crawling"),
        )
        return [_row_to_dict(c) for c in created]

    def run_initial_crawl(self, website_id: str, max_pages: int = 100) -> dict:
        """Crawl the website and persist pages to the Digital_Twin."""
        from onboarding.crawler import InitialCrawler

        row = self._repo.get_website(self._tenant_id, website_id)
        if row is None:
            raise OnboardingError(f"Website {website_id} not found")
        self._repo.update_website(
            self._tenant_id, website_id, onboarding_state="crawling"
        )
        crawler = InitialCrawler(
            self._crawler, self._digital_twin, tenant_id=self._tenant_id
        )
        summary = crawler.crawl(website_id, row.url, max_pages)
        self._crawled_pages[website_id] = summary.crawled_pages
        wp_pages_mapped = self._resolve_wp_identities()
        self._repo.update_website(
            self._tenant_id,
            website_id,
            onboarding_state=OnboardingStateMachine.transition("crawling", "building"),
            last_crawled_at=datetime.now(timezone.utc),
        )
        return {
            "website_id": website_id,
            "pages": summary.pages,
            "posts": summary.posts,
            "media": summary.media,
            "internal_links": summary.internal_links,
            "external_links": summary.external_links,
            "wp_pages_mapped": wp_pages_mapped,
        }

    def _resolve_wp_identities(self) -> int:
        """Populate the URL -> WordPress page/post mapping from a live listing.

        Best-effort: with no publishing adapter configured (read-only/demo/
        offline connections), or if the live listing call fails, this is a
        no-op returning ``0`` rather than failing the crawl step — the mapping
        is a prerequisite for autonomous execution, not for crawling/analysis.
        """
        if self._publishing_adapter is None:
            return 0
        try:
            live_pages = self._publishing_adapter.list_pages()
        except Exception:  # noqa: BLE001 - best-effort; crawl must not fail
            return 0
        wp_pages = [
            (page.link, page.id, "page")
            for page in live_pages
            if page.link
        ]
        if not wp_pages or not hasattr(self._digital_twin, "resolve_wp_identities"):
            return 0
        return self._digital_twin.resolve_wp_identities(self._tenant_id, wp_pages)

    def build_digital_twin(self, website_id: str) -> dict:
        """Build the digital twin from the crawled pages."""
        from onboarding.digital_twin import DigitalTwinBuilder

        row = self._repo.get_website(self._tenant_id, website_id)
        if row is None:
            raise OnboardingError(f"Website {website_id} not found")
        self._repo.update_website(
            self._tenant_id, website_id, onboarding_state="building"
        )
        # Load crawled pages from the most recent crawl (cached in memory).
        pages = self._crawled_pages.get(website_id, [])
        builder = DigitalTwinBuilder(
            self._digital_twin,
            self._check_engine,
            self._fix_generator,
            tenant_id=self._tenant_id,
        )
        result = builder.build(website_id, pages)
        self._repo.update_website(
            self._tenant_id,
            website_id,
            onboarding_state=OnboardingStateMachine.transition("building", "ready"),
            status="READY",
        )
        return {
            "website_id": website_id,
            "pages": result.pages,
            "internal_links": result.internal_links,
            "issues": result.issues,
            "suggestions": result.suggestions,
            "structured_data_pages": result.structured_data_pages,
            "canonical_pages": result.canonical_pages,
            "image_count": result.image_count,
        }


# --- Helpers ------------------------------------------------------------------


def _row_to_dict(row: Any) -> dict:
    """Convert an ORM row to a plain dict (excluding SQLAlchemy internals)."""
    if row is None:
        return {}
    out: dict[str, Any] = {}
    for key in type(row).__mapper__.columns.keys():
        value = getattr(row, key)
        if isinstance(value, datetime):
            value = value.isoformat()
        out[key] = value
    return out
