"""Prompt registry: capability name -> current prompt template (§6.2).

Lets the orchestrator look up "the current ``meta_generator`` prompt" without
hardcoding imports across the service layer, and lets future A/B prompt versions
be introduced behind the same lookup. Instances are constructed once and shared
(templates are stateless).
"""

from __future__ import annotations

from intelligence.errors import PromptError
from intelligence.prompts import ALL_PROMPT_TEMPLATES
from intelligence.prompts.base_prompt_template import BasePromptTemplate

__all__ = ["PromptRegistry", "default_prompt_registry"]


class PromptRegistry:
    """Maps a capability name to its current :class:`BasePromptTemplate`."""

    def __init__(self, templates: list[BasePromptTemplate] | None = None) -> None:
        chosen = (
            templates
            if templates is not None
            else [cls() for cls in ALL_PROMPT_TEMPLATES]
        )
        self._by_capability: dict[str, BasePromptTemplate] = {}
        for template in chosen:
            self._by_capability[template.capability] = template

    def get(self, capability: str) -> BasePromptTemplate:
        """Return the current template for ``capability`` or raise ``PromptError``."""
        template = self._by_capability.get(capability)
        if template is None:
            raise PromptError(f"No prompt template registered for {capability!r}.")
        return template

    def has(self, capability: str) -> bool:
        return capability in self._by_capability

    def capabilities(self) -> list[str]:
        return sorted(self._by_capability)


def default_prompt_registry() -> PromptRegistry:
    """Build a registry populated with all current prompt templates."""
    return PromptRegistry()
