"""Shared context passed to validators (§7).

Carries the ground truth a validator needs to sanity-check AI output: the
current (partial) KnowledgeObject, the prompt context that produced the output,
and lookups like the set of existing slugs (for collision checks) and the page's
image element ids (for OG image references). All optional so a validator can be
unit-tested in isolation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

__all__ = ["ValidationContext"]


@dataclass
class ValidationContext:
    capability: str = ""
    knowledge_object: Any = None  # KnowledgeObject (partial), avoids import cycle
    prompt_context: Any = None  # PromptContext
    observed_text: str = ""  # crawled plain text, for hallucination checks
    existing_slugs: set[str] = field(default_factory=set)
    page_element_ids: set[str] = field(default_factory=set)
    top_keywords: list[str] = field(default_factory=list)
