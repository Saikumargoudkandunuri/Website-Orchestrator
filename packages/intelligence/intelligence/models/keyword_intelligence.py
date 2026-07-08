"""Keyword Intelligence section of the SEO Knowledge Object (§4.4).

Mixed source: ``keyword_density`` and ``keyword_placement`` are **observed** —
computed deterministically from the crawled text, never AI-guessed — which gives
the validation layer (``keyword_sanity_validator``) a hard, cheap ground truth to
sanity-check AI keyword claims against. Everything else (focus keyphrase, intent,
gaps) is **inferred**.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

__all__ = [
    "SearchIntent",
    "NamedEntity",
    "KeywordPlacement",
    "KeywordIntelligenceSection",
]


class SearchIntent(str, Enum):
    INFORMATIONAL = "informational"
    NAVIGATIONAL = "navigational"
    TRANSACTIONAL = "transactional"
    COMMERCIAL_INVESTIGATION = "commercial_investigation"


class NamedEntity(BaseModel):
    text: str
    type: str = "other"  # person | org | place | product | other
    confidence: float | None = None


class KeywordPlacement(BaseModel):
    """Observed placement of the focus keyphrase across key on-page locations."""

    in_title: bool = False
    in_h1: bool = False
    in_first_100_words: bool = False
    in_meta_description: bool = False
    in_url: bool = False


class KeywordIntelligenceSection(BaseModel):
    primary_focus_keyphrase: str | None = None  # inferred, unless owner-provided
    owner_provided_focus_keyphrase: str | None = None  # tracked separately (proposed->approved override)
    secondary_keyphrases: list[str] = Field(default_factory=list)  # 3-5 target
    related_semantic_keywords: list[str] = Field(default_factory=list)
    named_entities: list[NamedEntity] = Field(default_factory=list)
    search_intent: SearchIntent | None = None
    keyword_density: dict[str, float] = Field(default_factory=dict)  # observed
    keyword_placement: KeywordPlacement = Field(default_factory=KeywordPlacement)  # observed
    keyword_variations: list[str] = Field(default_factory=list)
    missing_important_keywords: list[str] = Field(default_factory=list)  # inferred gap
    source: str = "mixed"
