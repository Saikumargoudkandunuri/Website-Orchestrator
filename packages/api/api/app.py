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
    brain: object | None = None,
    agentic_planning: object | None = None,
    goal_repo: object | None = None,
    agentic_memory: object | None = None,
    agentic_runtime: object | None = None,
    agentic_reflection: object | None = None,
    agentic_agents: object | None = None,
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
        and automatic OpenAPI docs at ``/docs (Req 10.9).
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
    _mount_brain(app, brain=brain, is_production=is_production)
    _mount_agentic(
        app,
        agentic_planning=agentic_planning,
        goal_repo=goal_repo,
        is_production=is_production,
    )
    _mount_agentic_memory(
        app,
        agentic_memory=agentic_memory,
        is_production=is_production,
    )
    _mount_agentic_runtime(
        app,
        agentic_runtime=agentic_runtime,
        is_production=is_production,
    )
    _mount_agentic_reflection(
        app,
        agentic_reflection=agentic_reflection,
        is_production=is_production,
    )
    _mount_agentic_agents(
        app,
        agentic_agents=agentic_agents,
        is_production=is_production,
    )
    _mount_saas(app, is_production=is_production)
    return app







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


def _mount_brain(app: FastAPI, *, brain: object | None, is_production: bool) -> None:
    """Mount the Milestone 5 brain router additively."""
    from brain.api import BrainContainer, build_default_brain, build_brain_router

    container = brain
    if container is None and is_production:
        try:
            from core.config import get_settings

            if get_settings().brain_engine_enabled:
                container = build_default_brain()
        except Exception:  # noqa: BLE001 - no config/datastore => do not mount
            container = None
    if container is None:
        return
    if not isinstance(container, BrainContainer):  # pragma: no cover - defensive
        return
    app.state.brain = container
    app.include_router(build_brain_router())


def _mount_agentic(
    app: FastAPI,
    *,
    agentic_planning: object | None,
    goal_repo: object | None,
    is_production: bool,
) -> None:
    """Mount the Milestone 6 agentic planning router additively."""
    from agentic.planning.wiring import PlanningContainer, build_planning_container
    from agentic.planning.api import build_planning_router
    from agentic.goal.repositories import InMemoryGoalRepository, SqlAlchemyGoalRepository
    from agentic.tools.registry import build_default_tool_registry
    from intelligence.ai.providers.fake_provider import FakeProvider

    container = agentic_planning
    resolved_goal_repo = goal_repo

    if container is None and is_production:
        try:
            from core.config import get_settings
            from digital_twin.db import create_db_engine, make_session_factory
            from brain.db import BrainBase

            settings = get_settings()
            if getattr(settings, "agentic_engine_enabled", True):
                engine = create_db_engine(settings.database_url)
                # Ensure agentic tables exist in the DB
                from agentic.planning.repositories import PlanRecord, ExecutionGraphRecord, SimulationRecord
                from agentic.goal.repositories import GoalRecord
                BrainBase.metadata.create_all(engine)
                session_factory = make_session_factory(engine)
                
                # Resolve brain container and intelligence provider
                brain_container = getattr(app.state, "brain", None)
                intel_container = getattr(app.state, "intelligence", None)
                
                provider = intel_container.provider if intel_container else FakeProvider()
                registry = build_default_tool_registry()
                
                if brain_container:
                    container = build_planning_container(
                        session_factory,
                        settings.tenant_id,
                        provider=provider,
                        registry=registry,
                        kg_repo=brain_container.kg_repo,
                        historical_repo=brain_container.historical_repo,
                        decision_engine=brain_container.decision_engine,
                    )
                
                if resolved_goal_repo is None:
                    resolved_goal_repo = SqlAlchemyGoalRepository(session_factory, tenant_id=settings.tenant_id)
        except Exception:
            container = None
            resolved_goal_repo = None

    if container is None:
        # Fallback/tests default if not fully set up
        if getattr(app.state, "brain", None):
            brain_container = app.state.brain
            intel_container = getattr(app.state, "intelligence", None)
            provider = intel_container.provider if intel_container else FakeProvider()
            registry = build_default_tool_registry()
            
            # Simple mock/in-memory session_source for fallback
            from sqlalchemy import create_engine
            from sqlalchemy.orm import sessionmaker
            fallback_engine = create_engine("sqlite:///:memory:")
            from brain.db import BrainBase
            BrainBase.metadata.create_all(fallback_engine)
            fallback_session_factory = sessionmaker(bind=fallback_engine)
            
            container = build_planning_container(
                fallback_session_factory,
                "default",
                provider=provider,
                registry=registry,
                kg_repo=brain_container.kg_repo,
                historical_repo=brain_container.historical_repo,
                decision_engine=brain_container.decision_engine,
            )
            if resolved_goal_repo is None:
                resolved_goal_repo = InMemoryGoalRepository()
        else:
            return

    app.state.agentic_planning = container
    app.state.goal_repository = resolved_goal_repo
    app.include_router(build_planning_router())


def _mount_agentic_memory(
    app: FastAPI,
    *,
    agentic_memory: object | None,
    is_production: bool,
) -> None:
    """Mount the Milestone 6 cognitive memory router additively."""
    from agentic.memory.wiring import MemoryContainer, build_memory_container
    from agentic.memory.api import build_memory_router

    container = agentic_memory

    if container is None and is_production:
        try:
            from core.config import get_settings
            from digital_twin.db import create_db_engine, make_session_factory
            from brain.db import BrainBase

            settings = get_settings()
            if getattr(settings, "agentic_engine_enabled", True):
                engine = create_db_engine(settings.database_url)
                # Ensure memory tables exist
                from agentic.memory.repositories import (
                    EpisodeRecord,
                    SemanticFactRecord,
                    WorkflowTemplateRecord,
                    ReflectionLessonRecord,
                    GoalMemoryRecordRow,
                    MemoryIndexRecord,
                )
                BrainBase.metadata.create_all(engine)
                session_factory = make_session_factory(engine)
                
                # Retrieve upstream references from other containers if available
                brain_container = getattr(app.state, "brain", None)
                intel_container = getattr(app.state, "intelligence", None)
                
                ko_repo = intel_container.knowledge_repo if intel_container else None
                ai_invocation_repo = intel_container.invocation_repo if intel_container else None
                
                kg_repo = brain_container.kg_repo if brain_container else None
                decision_repo = brain_container.decision_repo if brain_container else None
                synthesis_repo = brain_container.synthesis_repo if brain_container else None
                historical_repo = brain_container.historical_repo if brain_container else None
                
                container = build_memory_container(
                    session_factory,
                    settings.tenant_id,
                    ko_repo=ko_repo,
                    kg_repo=kg_repo,
                    decision_repo=decision_repo,
                    synthesis_repo=synthesis_repo,
                    historical_repo=historical_repo,
                    ai_invocation_repo=ai_invocation_repo,
                )
        except Exception:
            container = None

    if container is None:
        # Fallback/tests default if not fully set up
        intel_container = getattr(app.state, "intelligence", None)
        brain_container = getattr(app.state, "brain", None)
        
        # Instantiate a clean sqlite database for tests
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy.pool import StaticPool
        
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        from brain.db import BrainBase
        from agentic.memory.repositories import (
            EpisodeRecord,
            SemanticFactRecord,
            WorkflowTemplateRecord,
            ReflectionLessonRecord,
            GoalMemoryRecordRow,
            MemoryIndexRecord,
        )
        BrainBase.metadata.create_all(engine)
        session_factory = sessionmaker(bind=engine)
        
        ko_repo = intel_container.knowledge_repo if intel_container else None
        ai_invocation_repo = intel_container.invocation_repo if intel_container else None
        
        kg_repo = brain_container.kg_repo if brain_container else None
        decision_repo = brain_container.decision_repo if brain_container else None
        synthesis_repo = brain_container.synthesis_repo if brain_container else None
        historical_repo = brain_container.historical_repo if brain_container else None
        
        container = build_memory_container(
            session_factory,
            "default",
            ko_repo=ko_repo,
            kg_repo=kg_repo,
            decision_repo=decision_repo,
            synthesis_repo=synthesis_repo,
            historical_repo=historical_repo,
            ai_invocation_repo=ai_invocation_repo,
        )

    app.state.agentic_memory = container
    app.include_router(build_memory_router())


def _mount_agentic_runtime(
    app: FastAPI,
    *,
    agentic_runtime: object | None,
    is_production: bool,
) -> None:
    """Mount the Milestone 6 agentic runtime router additively."""
    from agentic.runtime.wiring import RuntimeContainer, build_runtime_container
    from agentic.runtime.api import build_runtime_router
    from agentic.tools.registry import build_default_tool_registry

    container = agentic_runtime

    if container is None and is_production:
        try:
            from core.config import get_settings
            from digital_twin.db import create_db_engine, make_session_factory
            from brain.db import BrainBase

            settings = get_settings()
            if getattr(settings, "agentic_engine_enabled", True):
                engine = create_db_engine(settings.database_url)
                # Ensure runtime tables exist
                from agentic.runtime.repositories import CheckpointRecord, ExecutionRecordRow, ExecutionMetricsRecord
                BrainBase.metadata.create_all(engine)
                session_factory = make_session_factory(engine)
                
                # Fetch memory manager and registry
                memory_container = getattr(app.state, "agentic_memory", None)
                registry = build_default_tool_registry()
                
                if memory_container:
                    container = build_runtime_container(
                        session_factory,
                        settings.tenant_id,
                        registry=registry,
                        memory_manager=memory_container.manager,
                    )
        except Exception:
            container = None

    if container is None:
        # Fallback/tests default if not fully set up
        memory_container = getattr(app.state, "agentic_memory", None)
        registry = build_default_tool_registry()
        
        # Instantiate sqlite engine for tests
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy.pool import StaticPool
        
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        from brain.db import BrainBase
        from agentic.runtime.repositories import CheckpointRecord, ExecutionRecordRow, ExecutionMetricsRecord
        BrainBase.metadata.create_all(engine)
        session_factory = sessionmaker(bind=engine)
        
        if memory_container:
            container = build_runtime_container(
                session_factory,
                "default",
                registry=registry,
                memory_manager=memory_container.manager,
            )

    app.state.agentic_runtime = container
    if container:
        app.include_router(build_runtime_router())


def _mount_agentic_reflection(
    app: FastAPI,
    *,
    agentic_reflection: object | None,
    is_production: bool,
) -> None:
    """Mount the Milestone 6 agentic reflection/learning router additively."""
    from agentic.reflection.wiring import ReflectionContainer, build_reflection_container
    from agentic.reflection.api import build_reflection_router

    container = agentic_reflection

    if container is None and is_production:
        try:
            from core.config import get_settings
            from digital_twin.db import create_db_engine, make_session_factory
            from brain.db import BrainBase

            settings = get_settings()
            if getattr(settings, "agentic_engine_enabled", True):
                engine = create_db_engine(settings.database_url)
                # Ensure reflection tables exist
                from agentic.reflection.repositories import (
                    ReflectionReportRecord,
                    ProviderScoreRecord,
                    ToolScoreRecord,
                    ConfidenceCalibrationRecord,
                )
                BrainBase.metadata.create_all(engine)
                session_factory = make_session_factory(engine)
                
                # Fetch memory container
                memory_container = getattr(app.state, "agentic_memory", None)
                
                if memory_container:
                    container = build_reflection_container(
                        session_factory,
                        settings.tenant_id,
                        memory_manager=memory_container.manager,
                    )
        except Exception:
            container = None

    if container is None:
        # Fallback/tests default if not fully set up
        memory_container = getattr(app.state, "agentic_memory", None)
        
        # Instantiate sqlite engine for tests
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy.pool import StaticPool
        
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        from brain.db import BrainBase
        from agentic.reflection.repositories import (
            ReflectionReportRecord,
            ProviderScoreRecord,
            ToolScoreRecord,
            ConfidenceCalibrationRecord,
        )
        BrainBase.metadata.create_all(engine)
        session_factory = sessionmaker(bind=engine)
        
        if memory_container:
            container = build_reflection_container(
                session_factory,
                "default",
                memory_manager=memory_container.manager,
            )

    app.state.agentic_reflection = container
    if container:
        app.include_router(build_reflection_router())


def _mount_agentic_agents(
    app: FastAPI,
    *,
    agentic_agents: object | None,
    is_production: bool,
) -> None:
    """Mount the Milestone 6 multi-agent router additively."""
    from agentic.agents.wiring import AgentContainer, build_agent_container
    from agentic.agents.api import build_agent_router

    container = agentic_agents

    if container is None and is_production:
        try:
            from core.config import get_settings
            from digital_twin.db import create_db_engine, make_session_factory
            from brain.db import BrainBase

            settings = get_settings()
            if getattr(settings, "agentic_engine_enabled", True):
                engine = create_db_engine(settings.database_url)
                # Ensure agent tables exist
                from agentic.agents.repositories import (
                    MissionRecord,
                    BlackboardEntryRecord,
                    MessageRecord,
                )
                BrainBase.metadata.create_all(engine)
                session_factory = make_session_factory(engine)
                
                # Fetch runtime container
                runtime_container = getattr(app.state, "agentic_runtime", None)
                
                if runtime_container:
                    container = build_agent_container(
                        session_factory,
                        settings.tenant_id,
                        runtime=runtime_container.runtime,
                    )
        except Exception:
            container = None

    if container is None:
        # Fallback/tests default if not fully set up
        runtime_container = getattr(app.state, "agentic_runtime", None)
        
        # Instantiate sqlite engine for tests
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy.pool import StaticPool
        
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        from brain.db import BrainBase
        from agentic.agents.repositories import (
            MissionRecord,
            BlackboardEntryRecord,
            MessageRecord,
        )
        BrainBase.metadata.create_all(engine)
        session_factory = sessionmaker(bind=engine)
        
        if runtime_container:
            container = build_agent_container(
                session_factory,
                "default",
                runtime=runtime_container.runtime,
            )

    app.state.agentic_agents = container
    if container:
        app.include_router(build_agent_router())






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
        try:
            from observability.aggregator import get_aggregator
            get_aggregator().record_error(exc, context={"url": request.url._url})
        except ImportError:
            pass  # Fail gracefully if not installed
        
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
        try:
            from observability.aggregator import get_aggregator
            get_aggregator().record_error(exc, context={"url": request.url._url, "status_code": status_code})
        except ImportError:
            pass
            
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
        try:
            from observability.aggregator import get_aggregator
            get_aggregator().record_error(exc, context={"url": request.url._url})
        except ImportError:
            pass
            
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


def _mount_saas(app: FastAPI, is_production: bool) -> None:
    """Mount all SaaS experience modules (workspace, enterprise, analytics, automation, collab, copilot, marketplace) additively."""
    try:
        from core.config import get_settings
        from digital_twin.db import create_db_engine, make_session_factory
        from saas.db import create_saas_tables
        from intelligence.ai.providers.fake_provider import FakeProvider

        settings = get_settings()
        engine = create_db_engine(settings.database_url)
        create_saas_tables(engine)
        session_factory = make_session_factory(engine)
        
        # Instantiate Workspace
        from saas.workspace.repositories import WorkspaceRepository, CanvasRepository
        from saas.workspace.services import (
            WorkspaceService,
            CanvasService,
            CommandPaletteService,
            DashboardBuilderService,
        )
        from saas.workspace.api import build_workspace_router
        ws_repo = WorkspaceRepository(session_factory, tenant_id=settings.tenant_id)
        canvas_repo = CanvasRepository(session_factory, tenant_id=settings.tenant_id)
        ws_service = WorkspaceService(ws_repo)
        canvas_service = CanvasService(canvas_repo)
        cmd_service = CommandPaletteService()
        app.include_router(build_workspace_router(ws_service, canvas_service, cmd_service))

        # Instantiate Enterprise
        from saas.enterprise.repositories import EnterpriseRepository
        from saas.enterprise.services import (
            AccessControlService,
            UsageMeterService,
            AuditLogService,
            StripeService,
        )
        from saas.enterprise.api import build_enterprise_router
        ent_repo = EnterpriseRepository(session_factory, tenant_id=settings.tenant_id)
        rbac = AccessControlService(ent_repo)
        meter = UsageMeterService()
        audit = AuditLogService(ent_repo)
        stripe = StripeService()
        app.include_router(build_enterprise_router(rbac, meter, audit, stripe))

        # Instantiate Analytics
        from saas.analytics.repositories import AnalyticsRepository
        from saas.analytics.services import (
            AnalyticsAggregatorService,
            ReportGeneratorService,
            KPIEvaluatorService,
            AlertRuleService,
        )
        from saas.analytics.api import build_analytics_router
        analytics_repo = AnalyticsRepository(session_factory, tenant_id=settings.tenant_id)
        aggregator = AnalyticsAggregatorService(analytics_repo)
        generator = ReportGeneratorService()
        kpi = KPIEvaluatorService()
        alerts = AlertRuleService(analytics_repo)
        app.include_router(build_analytics_router(aggregator, generator, kpi, alerts))

        # Instantiate Automation
        from saas.automation.repositories import AutomationRepository
        from saas.automation.services import (
            AutomationEngineService,
            SandboxRunnerService,
            NotificationAdapterService,
        )
        from saas.automation.api import build_automation_router
        auto_repo = AutomationRepository(session_factory, tenant_id=settings.tenant_id)
        sandbox = SandboxRunnerService()
        notifier = NotificationAdapterService()
        engine_service = AutomationEngineService(auto_repo, sandbox, notifier)
        app.include_router(build_automation_router(engine_service))

        # Instantiate Collaboration
        from saas.collaboration.repositories import CollaborationRepository
        from saas.collaboration.services import (
            ThreadService,
            DecisionLogService,
            NotificationService,
        )
        from saas.collaboration.api import build_collaboration_router
        collab_repo = CollaborationRepository(session_factory, tenant_id=settings.tenant_id)
        threads = ThreadService(collab_repo)
        decisions = DecisionLogService(collab_repo)
        notifications = NotificationService(collab_repo)
        app.include_router(build_collaboration_router(threads, decisions, notifications))

        # Instantiate Copilot
        from saas.copilot.repositories import CopilotRepository
        from saas.copilot.services import (
            CopilotService,
            ContextCollectorService,
            ExplanationEngineService,
        )
        from saas.copilot.api import build_copilot_router
        copilot_repo = CopilotRepository(session_factory, tenant_id=settings.tenant_id)
        
        intel_container = getattr(app.state, "intelligence", None)
        provider = intel_container.provider if intel_container else FakeProvider()
        copilot_service = CopilotService(copilot_repo, provider)
        collector = ContextCollectorService()
        explanations = ExplanationEngineService(copilot_repo)
        app.include_router(build_copilot_router(copilot_service, collector, explanations))

        # Instantiate Marketplace
        from saas.marketplace.repositories import MarketplaceRepository
        from saas.marketplace.services import (
            AppRegistryService,
            AppInstallationService,
            OAuthServerService,
        )
        from saas.marketplace.api import build_marketplace_router
        market_repo = MarketplaceRepository(session_factory, tenant_id=settings.tenant_id)
        registry = AppRegistryService(market_repo)
        installer = AppInstallationService(market_repo)
        oauth = OAuthServerService()
        app.include_router(build_marketplace_router(registry, installer, oauth))

    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("SaaS Platform experiences routing skipped: %s", e)
