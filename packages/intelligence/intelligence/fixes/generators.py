"""Milestone-2 fix generators for metadata/title/slug/schema (§8.2).

Each reads a specific proposed field from the KnowledgeObject and packages it as
a Milestone 1 :class:`~core.types.SuggestedFix`. Registering a new fix type is
exactly a matter of adding one of these — the Milestone 1 FixGenerator interface
and the Governance/Publisher pipeline are untouched.
"""

from __future__ import annotations

from intelligence.fixes.base import KnowledgeObjectFixGenerator
from intelligence.models.knowledge_object import KnowledgeObject

__all__ = [
    "MetaDescriptionFixGenerator",
    "TitleFixGenerator",
    "SlugFixGenerator",
    "SchemaFixGenerator",
    "ALL_KO_FIX_GENERATORS",
]


class MetaDescriptionFixGenerator(KnowledgeObjectFixGenerator):
    kind = "update_meta_description"

    def proposed_value(self, ko: KnowledgeObject) -> str | None:
        return ko.metadata.meta_description.proposed_value

    def reasoning(self, ko: KnowledgeObject) -> str | None:
        return ko.metadata.meta_description.proposed_reasoning


class TitleFixGenerator(KnowledgeObjectFixGenerator):
    kind = "update_title"

    def proposed_value(self, ko: KnowledgeObject) -> str | None:
        return ko.metadata.seo_title.proposed_value

    def reasoning(self, ko: KnowledgeObject) -> str | None:
        return ko.metadata.seo_title.proposed_reasoning


class SlugFixGenerator(KnowledgeObjectFixGenerator):
    kind = "update_slug"

    def proposed_value(self, ko: KnowledgeObject) -> str | None:
        return ko.identity.proposed_slug.proposed_value

    def reasoning(self, ko: KnowledgeObject) -> str | None:
        return ko.identity.proposed_slug.proposed_reasoning


class SchemaFixGenerator(KnowledgeObjectFixGenerator):
    kind = "update_schema"

    def proposed_value(self, ko: KnowledgeObject) -> str | None:
        blocks = ko.schema_intelligence.generated_jsonld
        return blocks[0].raw_jsonld if blocks else None

    def reasoning(self, ko: KnowledgeObject) -> str | None:
        recs = ko.schema_intelligence.recommended_schema
        return recs[0].reasoning if recs else None


#: All KnowledgeObject-driven fix generators, in a stable order.
ALL_KO_FIX_GENERATORS: tuple[type[KnowledgeObjectFixGenerator], ...] = (
    MetaDescriptionFixGenerator,
    TitleFixGenerator,
    SlugFixGenerator,
    SchemaFixGenerator,
)
