"""AI_Generator subsystem — real AI-backed content generation (Milestone 1).

Proposes real, accessible alt text through the
:class:`~core.interfaces.AltTextGenerationService` contract, replacing the
Milestone 0 filename heuristic. It only *proposes* content: it never writes to
the Digital_Twin and never publishes to the live site. The concrete LLM vendor
sits behind the injectable :class:`~core.interfaces.LLMClient` seam, so tests use
a network-free double. Depends only on Core_Package.
"""

from ai_generator.llm import HttpLLMClient, StaticLLMClient
from ai_generator.service import (
    DeterministicAltTextGenerationService,
    LlmAltTextGenerationService,
)

__all__ = [
    "HttpLLMClient",
    "StaticLLMClient",
    "LlmAltTextGenerationService",
    "DeterministicAltTextGenerationService",
]
