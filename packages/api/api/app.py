"""API_Surface — the FastAPI application factory and composition root.

:func:`create_app` builds the FastAPI application, wires the subsystem
dependency-injection container onto ``app.state``, registers the route handlers,
and maps subsystem errors to HTTP responses. FastAPI publishes automatic
OpenAPI documentation at ``/docs`` (Req 10.9).

Route handlers are deliberately **thin**: they delegate to the subsystem
contracts and hold no business logic (Req 10.10). ``POST /crawl`` delegates the
whole crawl->check->fix loop to :func:`api.orchestration.run_crawl` and returns
the resulting :class:`~core.types.CrawlSummary` (Req 10.1).

Dependency injection
--------------------
``create_app`` accepts optional subsystem instances. When every subsystem is
supplied it is used as-is — this is how tests inject network-free fakes (an
in-memory SQLite :class:`~digital_twin.repository.DigitalTwinRepository`, a fake
Crawler returning canned pages, and so on). When they are omitted the
production bundle is built from configuration via
:func:`api.container.build_default_subsystems` (the live PostgreSQL datastore
and WordPress client, Req 10.8). Either way the resulting
:class:`~api.container.Subsystems` bundle is stashed on ``app.state`` for the
request-scoped providers in :mod:`api.dependencies`.

The read endpoints (``GET /issues``, ``GET /fixes``, ``GET /audit-log``) are thin
delegators to the Digital_Twin (Req 10.2, 10.3, 10.7). The decision endpoints
(``POST /fixes/{id}/approve|reject|rollback``) are equally thin delegators to the
Governance_Layer (Req 10.4-10.6): each first looks the fix up via the Digital_Twin
and returns a ``404`` without invoking governance when the id identifies no
persisted fix (Req 10.12), and any Governance_Layer/Publishing_Adapter failure is
mapped to an explicit HTTP failure response reporting the reason — never a success
(Req 10.13).
"""

from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.requests import Request

from core.exceptions import (
    FixAlreadyDecidedError,
    FixNotFoundError,
    GovernanceError,
    InvalidCrawlRequest,
    InvalidDecisionError,
    PublishingError,
    RollbackNotAllowedError,
)
from core.interfaces import (
    CheckEnginePort,
    CrawlerPort,
    DigitalTwinPort,
    FixGeneratorPort,
    GovernancePort,
)
from core.types import AuditEntry, CrawlSummary, Issue, SuggestedFix

from api.container import Subsystems, build_default_subsystems
from api.dependencies import (
    get_check_engine,
    get_crawler,
    get_digital_twin,
    get_fix_generator,
    get_governance,
    get_tenant_id,
)
from api.orchestration import run_crawl
from api.schemas import CrawlRequest, DecisionRequest

__all__ = ["create_app"]


def create_app(
    *,
    crawler: CrawlerPort | None = None,
    digital_twin: DigitalTwinPort | None = None,
    check_engine: CheckEnginePort | None = None,
    fix_generator: FixGeneratorPort | None = None,
    governance: GovernancePort | None = None,
    tenant_id: str | None = None,
    subsystems: Subsystems | None = None,
    intelligence: object | None = None,
    growth: object | None = None,
    onboarding: object | None = None,
) -> FastAPI:
    """Create and configure the Website Orchestrator FastAPI application.

    Parameters
    ----------
    crawler, digital_twin, check_engine, fix_generator, governance:
        Optional subsystem contracts. When **all** are supplied (typically
        in-memory fakes under test) they are bundled and used directly. When any
        is omitted the full production bundle is built from configuration.
    tenant_id:
        The configured Tenant_Id every persistence call is scoped to. Required
        when injecting subsystems explicitly; otherwise taken from settings.
    subsystems:
        A pre-built :class:`~api.container.Subsystems` bundle. When supplied it
        takes precedence over the individual arguments — the single most direct
        injection point for tests.

    Returns
    -------
    FastAPI
        The configured application, with the subsystem bundle on ``app.state``
        and automatic OpenAPI docs at ``/docs`` (Req 10.9).
    """
    app = FastAPI(
        title="Website Orchestrator API",
        version="0.1.0",
        summary=(
            "Crawl a site, detect issues, generate fixes, and drive the "
            "human-approved publish/rollback loop."
        ),
    )

    app.state.subsystems = _resolve_subsystems(
        subsystems=subsystems,
        crawler=crawler,
        digital_twin=digital_twin,
        check_engine=check_engine,
        fix_generator=fix_generator,
        governance=governance,
        tenant_id=tenant_id,
    )

    _register_exception_handlers(app)
    _register_routes(app)
    is_production = subsystems is None and all(
        part is None
        for part in (crawler, digital_twin, check_engine, fix_generator, governance)
    )
    _mount_intelligence(
        app,
        intelligence=intelligence,
        is_production=is_production,
    )
    _mount_growth(app, growth=growth, is_production=is_production)
    _mount_seo(app)
    _mount_onboarding(app, onboarding=onboarding, is_production=is_production)
    _mount_agentic_and_platform(app)
    return app


def _mount_seo(app: FastAPI) -> None:
    """Mount the SEO engine router (6 priority phases) additively."""
    from api.seo_router import build_properties_router, build_seo_router

    app.include_router(build_seo_router())
    app.include_router(build_properties_router())


def _mount_agentic_and_platform(app: FastAPI) -> None:
    """Mount the agentic AI, copilot, executive-dashboard and SaaS-surface
    routers additively so the console's remaining features are reachable.

    The agentic loop reuses the existing subsystems (crawler, digital_twin,
    check_engine, fix_generator, governance) via ``app.state.subsystems`` and
    never introduces an unattended publish path — every edit still flows through
    the Governance_Layer. Wrapped defensively so a wiring failure degrades to
    "feature not mounted" instead of failing app startup.
    """
    try:
        from api.agent_router import (
            build_agent_router,
            build_copilot_router,
            build_executive_router,
            configure_cmo_scheduler,
        )
        from api.saas_stub_router import build_saas_stub_router

        app.include_router(build_agent_router())
        app.include_router(build_copilot_router())
        app.include_router(build_executive_router())
        app.include_router(build_saas_stub_router())

        # Production can opt into unattended wakeups explicitly. The safe
        # default is off; when enabled, every tick still honors per-site flags,
        # governance mode, audit, and rollback policy.
        try:
            from core.config import get_settings

            if get_settings().cmo_scheduler_enabled:
                configure_cmo_scheduler(app)
        except Exception:  # noqa: BLE001 - scheduler is additive
            pass
    except Exception:  # noqa: BLE001 - additive; never break existing surface
        pass


def _mount_onboarding(
    app: FastAPI, *, onboarding: object | None, is_production: bool
) -> None:
    """Mount the Foundation onboarding router additively (never replacing M1)."""
    from onboarding.routes import build_onboarding_router
    from onboarding.services import (
        ConnectionService,
        OnboardingOrchestrator,
        ProjectService,
        WebsiteService,
        WorkspaceService,
    )
    from onboarding.repository import OnboardingRepository

    container = onboarding
    if container is None and is_production:
        try:
            from core.config import get_settings

            settings = get_settings()
            # Reuse the live Digital_Twin session factory for onboarding storage.
            from digital_twin.db import create_db_engine, make_session_factory
            from digital_twin.models import Base
            from onboarding.models import Base as OnboardingBase

            engine = create_db_engine(settings.database_url)
            Base.metadata.create_all(engine)
            OnboardingBase.metadata.create_all(engine)
            session_factory = make_session_factory(engine)
            repo = OnboardingRepository(session_factory, tenant_id=settings.tenant_id)

            from crawler import Crawler
            from check_engine import CheckEngine
            from fix_generator import FixGenerator
            from digital_twin.repository import DigitalTwinRepository
            from publishing_adapter import WordPressClient

            digital_twin = DigitalTwinRepository(
                session_factory, tenant_id=settings.tenant_id
            )
            publishing = WordPressClient(
                settings.wp_base_url,
                settings.wp_username,
                settings.wp_application_password,
            )
            workspace_service = WorkspaceService(repo)
            project_service = ProjectService(repo)
            website_service = WebsiteService(repo)
            connection_service = ConnectionService(repo, publishing_adapter=publishing)
            orchestrator = OnboardingOrchestrator(
                repo,
                crawler=Crawler(),
                digital_twin=digital_twin,
                check_engine=CheckEngine(),
                fix_generator=FixGenerator(),
                publishing_adapter=publishing,
                tenant_id=settings.tenant_id,
            )
            container = {
                "workspace_service": workspace_service,
                "project_service": project_service,
                "website_service": website_service,
                "connection_service": connection_service,
                "orchestrator": orchestrator,
                "tenant_id": settings.tenant_id,
            }
        except Exception:  # noqa: BLE001 - no config/datastore => do not mount
            container = None
    if container is None:
        return
    if not isinstance(container, dict):  # pragma: no cover - defensive
        return

    # Expose the exact onboarding persistence boundary used by the HTTP routes.
    # The autonomous CMO uses this shared instance for tenant/site-scoped memory
    # and connected-site discovery instead of opening a divergent repository.
    state_container = dict(container)
    state_container.setdefault(
        "repository", getattr(container.get("website_service"), "_repo", None)
    )
    app.state.onboarding = state_container
    app.include_router(
        build_onboarding_router(
            workspace_service=container["workspace_service"],
            project_service=container["project_service"],
            website_service=container["website_service"],
            connection_service=container["connection_service"],
            orchestrator=container["orchestrator"],
            tenant_id=container["tenant_id"],
        )
    )


def _mount_growth(app: FastAPI, *, growth: object | None, is_production: bool) -> None:
    """Mount the Milestone 4 growth router additively."""
    from growth.api import GrowthContainer, build_default_growth, build_growth_router

    container = growth
    if container is None and is_production:
        try:
            from core.config import get_settings

            if get_settings().growth_engine_enabled:
                container = build_default_growth()
        except Exception:  # noqa: BLE001 - no config/datastore => do not mount
            container = None
    if container is None:
        return
    if not isinstance(container, GrowthContainer):  # pragma: no cover - defensive
        return
    app.state.growth = container
    app.include_router(build_growth_router())

def _mount_intelligence(
    app: FastAPI, *, intelligence: object | None, is_production: bool
) -> None:
    """Mount the Milestone 2 intelligence router additively (never replacing M1).

    Uses an explicitly-injected container when provided (tests); otherwise, on
    the pure production path, builds the default container from configuration.
    If neither is available (e.g. Milestone 1 tests that inject subsystems and
    no intelligence), the router is simply not mounted, so existing behavior is
    untouched.
    """
    from intelligence.api import (
        IntelligenceContainer,
        build_default_intelligence,
        build_intelligence_router,
    )

    container = intelligence
    if container is None and is_production:
        try:
            from core.config import get_settings

            if get_settings().intelligence_engine_enabled:
                container = build_default_intelligence()
        except Exception:  # noqa: BLE001 - no config/datastore => don't mount
            container = None
    if container is None:
        return
    if not isinstance(container, IntelligenceContainer):  # pragma: no cover - defensive
        return
    app.state.intelligence = container
    app.include_router(build_intelligence_router())


def _resolve_subsystems(
    *,
    subsystems: Subsystems | None,
    crawler: CrawlerPort | None,
    digital_twin: DigitalTwinPort | None,
    check_engine: CheckEnginePort | None,
    fix_generator: FixGeneratorPort | None,
    governance: GovernancePort | None,
    tenant_id: str | None,
) -> Subsystems:
    """Resolve the subsystem bundle from the injection arguments.

    Precedence: an explicit ``subsystems`` bundle wins; otherwise, when every
    individual subsystem is supplied they are bundled (tenant required); if none
    are supplied the production bundle is built from configuration. A partial
    set of individual subsystems is a wiring error and is rejected.
    """
    if subsystems is not None:
        return subsystems

    provided = [crawler, digital_twin, check_engine, fix_generator, governance]
    if all(part is not None for part in provided):
        if tenant_id is None:
            raise ValueError(
                "tenant_id is required when injecting subsystems explicitly."
            )
        return Subsystems(
            crawler=crawler,  # type: ignore[arg-type]
            digital_twin=digital_twin,  # type: ignore[arg-type]
            check_engine=check_engine,  # type: ignore[arg-type]
            fix_generator=fix_generator,  # type: ignore[arg-type]
            governance=governance,  # type: ignore[arg-type]
            tenant_id=tenant_id,
        )
    if any(part is not None for part in provided):
        raise ValueError(
            "Inject either all subsystems (crawler, digital_twin, check_engine, "
            "fix_generator, governance) or none; a partial set is not supported."
        )

    return build_default_subsystems()


def _register_exception_handlers(app: FastAPI) -> None:
    """Map subsystem errors to explicit HTTP responses.

    An :class:`~core.exceptions.InvalidCrawlRequest` raised by the Crawler (a
    malformed start URL or out-of-range page count) becomes a ``422`` invalid-
    input response. Because the Crawler validates before retrieving anything, no
    crawl and no persistence has occurred by the time this fires (Req 10.11).
    """

    @app.exception_handler(InvalidCrawlRequest)
    async def _invalid_crawl_request(
        request: Request, exc: InvalidCrawlRequest
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"detail": f"Invalid crawl request: {exc}"},
        )

    @app.exception_handler(GovernanceError)
    async def _governance_error(
        request: Request, exc: GovernanceError
    ) -> JSONResponse:
        """Surface any Governance_Layer failure as an explicit HTTP failure
        reporting the reason, and never as success (Req 10.13).

        The status code narrows the failure so callers can react precisely while
        the ``detail`` always carries the reason:

        * :class:`~core.exceptions.FixNotFoundError` -> ``404`` (the fix
          disappeared between the pre-check and the decision, Req 8.9).
        * :class:`~core.exceptions.FixAlreadyDecidedError` /
          :class:`~core.exceptions.RollbackNotAllowedError` -> ``409`` (the fix
          is in a state that forbids the decision, Req 8.8, 9.1).
        * :class:`~core.exceptions.InvalidDecisionError` -> ``422`` (a missing
          actor or empty rationale reached governance, Req 8.11).
        * any other governance failure (for example a fail-closed
          BeforeReadError) -> ``502`` (the decision could not be completed).
        """
        status_code = _GOVERNANCE_STATUS.get(type(exc), 502)
        return JSONResponse(
            status_code=status_code,
            content={"detail": f"Governance decision failed: {exc}"},
        )

    @app.exception_handler(PublishingError)
    async def _publishing_error(
        request: Request, exc: PublishingError
    ) -> JSONResponse:
        """Surface a Publishing_Adapter failure raised while applying or rolling
        back a decision as a ``502`` failure reporting the reason, never as
        success (Req 10.13). No credential is ever present in a
        Publishing_Adapter error's message (Req 7.10), so echoing the reason is
        safe.
        """
        return JSONResponse(
            status_code=502,
            content={"detail": f"Publishing the decision failed: {exc}"},
        )


#: Maps a Governance_Layer error type to the HTTP status the API reports for it
#: (Req 10.13). Types absent from this mapping (including the ``GovernanceError``
#: base and ``BeforeReadError``) fall back to ``502``.
_GOVERNANCE_STATUS: dict[type[GovernanceError], int] = {
    FixNotFoundError: 404,
    FixAlreadyDecidedError: 409,
    RollbackNotAllowedError: 409,
    InvalidDecisionError: 422,
}


def _register_routes(app: FastAPI) -> None:
    """Register the API route handlers (thin delegators, Req 10.10)."""

    @app.post("/crawl", response_model=CrawlSummary, tags=["crawl"])
    def crawl(
        body: CrawlRequest,
        crawler: CrawlerPort = Depends(get_crawler),
        digital_twin: DigitalTwinPort = Depends(get_digital_twin),
        check_engine: CheckEnginePort = Depends(get_check_engine),
        fix_generator: FixGeneratorPort = Depends(get_fix_generator),
        tenant_id: str = Depends(get_tenant_id),
    ) -> CrawlSummary:
        """Crawl the site and return the summary (Req 10.1).

        A thin delegator: request-body validation rejects a blank start URL or a
        non-positive page count before this runs (Req 10.11), then the whole
        crawl->persist->check->persist->fix->persist loop is delegated to
        :func:`api.orchestration.run_crawl`. A malformed URL that passes body
        validation is rejected by the Crawler as
        :class:`~core.exceptions.InvalidCrawlRequest` and mapped to a ``422``
        with no persistence (Req 10.10, 10.11).
        """
        return run_crawl(
            body.start_url,
            body.max_pages,
            tenant_id=tenant_id,
            crawler=crawler,
            digital_twin=digital_twin,
            check_engine=check_engine,
            fix_generator=fix_generator,
        )

    @app.get("/issues", response_model=list[Issue], tags=["issues"])
    def list_issues(
        digital_twin: DigitalTwinPort = Depends(get_digital_twin),
        tenant_id: str = Depends(get_tenant_id),
    ) -> list[Issue]:
        """Return the persisted issues (Req 10.2).

        A thin delegator (Req 10.10): the Digital_Twin returns the tenant's
        persisted issues excluding those marked ignored.
        """
        return digital_twin.list_active_issues(tenant_id)

    @app.get("/fixes", response_model=list[SuggestedFix], tags=["fixes"])
    def list_fixes(
        digital_twin: DigitalTwinPort = Depends(get_digital_twin),
        tenant_id: str = Depends(get_tenant_id),
    ) -> list[SuggestedFix]:
        """Return the persisted suggested fixes (Req 10.3).

        A thin delegator (Req 10.10): the Digital_Twin returns all of the
        tenant's persisted suggested fixes regardless of status.
        """
        return digital_twin.list_fixes(tenant_id)

    def _require_persisted_fix(
        digital_twin: DigitalTwinPort, tenant_id: str, fix_id: str
    ) -> None:
        """Reject a decision whose ``fix_id`` identifies no persisted fix.

        Looks the fix up via the Digital_Twin **before** any Governance_Layer
        call; when it is absent this returns a ``404`` and the Governance_Layer
        is never invoked (Req 10.12). FastAPI renders the raised
        :class:`~fastapi.HTTPException` as a failure response carrying the
        not-found reason.
        """
        if digital_twin.get_fix(tenant_id, fix_id) is None:
            raise HTTPException(
                status_code=404,
                detail=f"Fix {fix_id!r} was not found.",
            )

    @app.post("/fixes/{id}/approve", response_model=SuggestedFix, tags=["fixes"])
    def approve_fix(
        id: str,
        body: DecisionRequest,
        governance: GovernancePort = Depends(get_governance),
        digital_twin: DigitalTwinPort = Depends(get_digital_twin),
        tenant_id: str = Depends(get_tenant_id),
    ) -> SuggestedFix:
        """Approve the fix ``id`` via the Governance_Layer (Req 10.4).

        A thin delegator (Req 10.10): an unknown id returns ``404`` without
        invoking governance (Req 10.12); otherwise the decision is delegated to
        :meth:`~core.interfaces.GovernancePort.approve_fix` and the updated fix
        is returned. Any governance/publishing error is mapped to an explicit
        HTTP failure by the registered handlers, never a success (Req 10.13).
        """
        _require_persisted_fix(digital_twin, tenant_id, id)
        return governance.approve_fix(tenant_id, id, body.actor, body.rationale)

    @app.post("/fixes/{id}/reject", response_model=SuggestedFix, tags=["fixes"])
    def reject_fix(
        id: str,
        body: DecisionRequest,
        governance: GovernancePort = Depends(get_governance),
        digital_twin: DigitalTwinPort = Depends(get_digital_twin),
        tenant_id: str = Depends(get_tenant_id),
    ) -> SuggestedFix:
        """Reject the fix ``id`` via the Governance_Layer (Req 10.5).

        A thin delegator (Req 10.10): an unknown id returns ``404`` without
        invoking governance (Req 10.12); otherwise the decision is delegated to
        :meth:`~core.interfaces.GovernancePort.reject_fix` and the updated fix is
        returned. Any governance error is mapped to an explicit HTTP failure by
        the registered handlers, never a success (Req 10.13).
        """
        _require_persisted_fix(digital_twin, tenant_id, id)
        return governance.reject_fix(tenant_id, id, body.actor, body.rationale)

    @app.post("/fixes/{id}/rollback", response_model=SuggestedFix, tags=["fixes"])
    def rollback_fix(
        id: str,
        body: DecisionRequest,
        governance: GovernancePort = Depends(get_governance),
        digital_twin: DigitalTwinPort = Depends(get_digital_twin),
        tenant_id: str = Depends(get_tenant_id),
    ) -> SuggestedFix:
        """Roll back the applied fix ``id`` via the Governance_Layer (Req 10.6).

        A thin delegator (Req 10.10): an unknown id returns ``404`` without
        invoking governance (Req 10.12); otherwise the decision is delegated to
        :meth:`~core.interfaces.GovernancePort.rollback_fix` and the updated fix
        is returned. Any governance/publishing error is mapped to an explicit
        HTTP failure by the registered handlers, never a success (Req 10.13).
        """
        _require_persisted_fix(digital_twin, tenant_id, id)
        return governance.rollback_fix(tenant_id, id, body.actor, body.rationale)

    @app.get("/audit-log", response_model=list[AuditEntry], tags=["audit"])
    def list_audit_log(
        digital_twin: DigitalTwinPort = Depends(get_digital_twin),
        tenant_id: str = Depends(get_tenant_id),
    ) -> list[AuditEntry]:
        """Return the Audit_Trail entries, most-recent first (Req 10.7).

        A thin delegator (Req 10.10): the Digital_Twin returns the tenant's
        Audit_Trail already ordered most-recent first.
        """
        return digital_twin.list_audit_entries(tenant_id)
