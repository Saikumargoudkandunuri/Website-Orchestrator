"""Intelligence API surface — additive FastAPI router + DI wiring (§10)."""

from intelligence.api.routes_intelligence import build_intelligence_router
from intelligence.api.wiring import (
    IntelligenceContainer,
    build_default_intelligence,
    build_intelligence_container,
)

__all__ = [
    "build_intelligence_router",
    "IntelligenceContainer",
    "build_intelligence_container",
    "build_default_intelligence",
]
