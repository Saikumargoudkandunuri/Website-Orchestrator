"""Provider-agnostic AI layer (§5).

Exposes the :class:`AIProvider` interface, the concrete adapters, the
configuration-driven factory, and the robust JSON parser. Everything outside
this subpackage depends on the interface, never on a concrete provider.
"""

from intelligence.ai.parsing import extract_json, strip_code_fences
from intelligence.ai.provider_factory import (
    SUPPORTED_PROVIDERS,
    ProviderConfig,
    build_provider,
)
from intelligence.ai.provider_interface import (
    AICompletionRequest,
    AICompletionResponse,
    AIProvider,
)

__all__ = [
    "AIProvider",
    "AICompletionRequest",
    "AICompletionResponse",
    "ProviderConfig",
    "build_provider",
    "SUPPORTED_PROVIDERS",
    "extract_json",
    "strip_code_fences",
]
