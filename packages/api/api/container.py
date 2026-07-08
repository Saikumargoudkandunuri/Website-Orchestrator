"""API_Surface composition root — the injectable subsystem container.

The API is the one place that wires the concrete subsystem implementations
together (:class:`~crawler.crawler.Crawler`,
:class:`~digital_twin.repository.DigitalTwinRepository`,
:class:`~check_engine.CheckEngine`, :class:`~fix_generator.FixGenerator`,
:class:`~publishing_adapter.WordPressClient`, and
:class:`~governance.service.GovernanceService`). Every subsystem is reachable
only through its Core_Package Protocol, so the API depends on those contracts
rather than on any subsystem's internals (Req 12.2).

:class:`Subsystems` is a simple, immutable bundle of those contracts plus the
configured Tenant_Id. It is built once per app — either from explicitly injected
instances (so tests can substitute in-memory fakes) or from Core_Package
configuration via :func:`build_default_subsystems` — and stashed on
``app.state`` for the request-scoped dependencies in :mod:`api.dependencies` to
read.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.interfaces import (
    CheckEnginePort,
    CrawlerPort,
    DigitalTwinPort,
    FixGeneratorPort,
    GovernancePort,
    PublishingAdapterPort,
)

__all__ = ["Subsystems", "build_default_subsystems"]


@dataclass(frozen=True)
class Subsystems:
    """The bundle of subsystem contracts the API delegates to.

    Every field is typed as the Core_Package Protocol the subsystem publishes,
    so the API_Surface never depends on a concrete implementation and tests can
    inject network-free fakes (Req 12.2).
    """

    crawler: CrawlerPort
    digital_twin: DigitalTwinPort
    check_engine: CheckEnginePort
    fix_generator: FixGeneratorPort
    governance: GovernancePort
    tenant_id: str


def build_default_subsystems() -> Subsystems:
    """Build the production :class:`Subsystems` bundle from configuration.

    Resolves settings (and the required WordPress ``Application_Password``
    secret) through :func:`core.config.get_settings`, opens the PostgreSQL
    datastore engine (Req 10.8), and constructs each concrete subsystem wired to
    the others through their Core_Package Protocols. The Publishing_Adapter is
    the sole live writer, injected into the Governance_Layer (Req 6.1, 8.2).

    Imports of the concrete subsystems are local to this function so that simply
    importing the app factory (for example to inject fakes in a test) never
    forces construction of the live datastore engine or the WordPress client.
    """
    from ai_generator import HttpLLMClient, LlmAltTextGenerationService
    from check_engine import CheckEngine
    from crawler import Crawler
    from digital_twin.db import create_db_engine, make_session_factory
    from digital_twin.models import Base
    from digital_twin.repository import DigitalTwinRepository
    from fix_generator import FixGenerator
    from governance.service import GovernanceService
    from publishing_adapter import WordPressClient

    from core.config import get_settings
    from core.interfaces import AltTextGenerationService

    settings = get_settings()

    engine = create_db_engine(settings.database_url)
    # The relational schema is managed by Alembic in production; ensure the
    # tables exist so a freshly-provisioned datastore is immediately usable.
    Base.metadata.create_all(engine)
    session_factory = make_session_factory(engine)

    digital_twin = DigitalTwinRepository(
        session_factory,
        tenant_id=settings.tenant_id,
        staleness_threshold=settings.staleness_threshold,
    )
    publishing_adapter: PublishingAdapterPort = WordPressClient(
        settings.wp_base_url,
        settings.wp_username,
        settings.wp_application_password,
    )
    governance = GovernanceService(digital_twin, publishing_adapter)

    # Milestone 1 — real AI alt-text generation is opt-in. When enabled, wire the
    # LLM-backed AltTextGenerationService into the Fix_Generator so
    # ``missing_alt_text`` fixes carry real AI suggestions with provenance; when
    # disabled (the default) the Fix_Generator keeps the Milestone 0 filename
    # heuristic. The AI layer only proposes content — Governance still gates every
    # publish, so enabling it never introduces an unattended auto-publish path.
    alt_text_service: AltTextGenerationService | None = None
    if settings.alt_text_ai_enabled:
        alt_text_service = LlmAltTextGenerationService(
            HttpLLMClient(
                settings.llm_base_url,
                settings.llm_model,
                settings.llm_api_key,
            ),
            model=settings.llm_model,
            max_output_tokens=settings.llm_max_output_tokens,
        )

    return Subsystems(
        crawler=Crawler(),
        digital_twin=digital_twin,
        check_engine=CheckEngine(),
        fix_generator=FixGenerator(alt_text_service),
        governance=governance,
        tenant_id=settings.tenant_id,
    )
