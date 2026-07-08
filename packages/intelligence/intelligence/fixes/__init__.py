"""Milestone-2 fix generators — package KnowledgeObject proposals as SuggestedFixes.

Reuse Milestone 1's :class:`~core.types.SuggestedFix` and Governance/Publisher
pipeline unchanged (§8.2).
"""

from intelligence.fixes.base import KnowledgeObjectFixGenerator
from intelligence.fixes.generators import (
    ALL_KO_FIX_GENERATORS,
    MetaDescriptionFixGenerator,
    SchemaFixGenerator,
    SlugFixGenerator,
    TitleFixGenerator,
)

__all__ = [
    "KnowledgeObjectFixGenerator",
    "MetaDescriptionFixGenerator",
    "TitleFixGenerator",
    "SlugFixGenerator",
    "SchemaFixGenerator",
    "ALL_KO_FIX_GENERATORS",
]
