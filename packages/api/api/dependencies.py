"""API_Surface dependency-injection wiring.

FastAPI resolves subsystem dependencies through these provider functions. Each
reads the :class:`~api.container.Subsystems` bundle stashed on ``app.state`` by
:func:`api.app.create_app`, so route handlers declare exactly the contract they
need (for example ``crawler: CrawlerPort = Depends(get_crawler)``) and stay
decoupled from construction. Tests substitute fakes simply by building the app
with injected instances; no dependency overrides are required (Req 12.2).
"""

from __future__ import annotations

from fastapi import Depends, Request

from core.interfaces import (
    CheckEnginePort,
    CrawlerPort,
    DigitalTwinPort,
    FixGeneratorPort,
    GovernancePort,
)

from api.container import Subsystems

__all__ = [
    "get_subsystems",
    "get_crawler",
    "get_digital_twin",
    "get_check_engine",
    "get_fix_generator",
    "get_governance",
    "get_tenant_id",
]


def get_subsystems(request: Request) -> Subsystems:
    """Return the :class:`Subsystems` bundle wired onto the app at startup."""
    return request.app.state.subsystems


def get_crawler(
    subsystems: Subsystems = Depends(get_subsystems),
) -> CrawlerPort:
    """Provide the Crawler contract."""
    return subsystems.crawler


def get_digital_twin(
    subsystems: Subsystems = Depends(get_subsystems),
) -> DigitalTwinPort:
    """Provide the Digital_Twin contract."""
    return subsystems.digital_twin


def get_check_engine(
    subsystems: Subsystems = Depends(get_subsystems),
) -> CheckEnginePort:
    """Provide the Check_Engine contract."""
    return subsystems.check_engine


def get_fix_generator(
    subsystems: Subsystems = Depends(get_subsystems),
) -> FixGeneratorPort:
    """Provide the Fix_Generator contract."""
    return subsystems.fix_generator


def get_governance(
    subsystems: Subsystems = Depends(get_subsystems),
) -> GovernancePort:
    """Provide the Governance_Layer contract."""
    return subsystems.governance


def get_tenant_id(
    subsystems: Subsystems = Depends(get_subsystems),
) -> str:
    """Provide the configured Tenant_Id every persistence call is scoped to."""
    return subsystems.tenant_id
