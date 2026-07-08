"""Typed models composing the SEO Knowledge Object (Milestone 2, §4).

Each section is a distinct typed structure that makes its Observation / Inference
/ Proposal category explicit (§1.3), never a flat untyped dict.
"""

from intelligence.models.ai_invocation import (
    AIInvocation,
    TokenUsage,
    ValidationOutcome,
)
from intelligence.models.content_intelligence import (
    ContentIntelligenceSection,
    ContentScore,
    ContentScoreFactor,
    PillarContentFlag,
)
from intelligence.models.eeat import EeatSection
from intelligence.models.identity import IdentitySection, PageType, UrlAnalysis
from intelligence.models.image_intelligence import (
    ImageIntelligenceSection,
    ImageRecord,
)
from intelligence.models.internal_seo import (
    InternalSeoSection,
    SuggestedExternalLink,
    SuggestedInternalLink,
)
from intelligence.models.keyword_intelligence import (
    KeywordIntelligenceSection,
    KeywordPlacement,
    SearchIntent,
)
from intelligence.models.knowledge_object import (
    DEFAULT_IMMUTABLE_FIELDS,
    AiIntelligenceSummary,
    FieldOverride,
    KnowledgeObject,
    PrioritizedImprovement,
    SeoRecommendation,
    SeoRecommendationPriority,
    SeoRecommendationStatus,
)
from intelligence.models.metadata_intelligence import (
    MetadataField,
    MetadataSection,
    OgImageField,
    OpenGraphData,
    OverrideSource,
)
from intelligence.models.schema_intelligence import (
    SchemaBlock,
    SchemaIntelligenceSection,
    SchemaValidationStatus,
)
from intelligence.models.technical_seo import TechnicalSeoSection

__all__ = [
    "AIInvocation",
    "TokenUsage",
    "ValidationOutcome",
    "ContentIntelligenceSection",
    "ContentScore",
    "ContentScoreFactor",
    "PillarContentFlag",
    "EeatSection",
    "IdentitySection",
    "PageType",
    "UrlAnalysis",
    "ImageIntelligenceSection",
    "ImageRecord",
    "InternalSeoSection",
    "SuggestedExternalLink",
    "SuggestedInternalLink",
    "KeywordIntelligenceSection",
    "KeywordPlacement",
    "SearchIntent",
    "KnowledgeObject",
    "AiIntelligenceSummary",
    "PrioritizedImprovement",
    "SeoRecommendation",
    "SeoRecommendationStatus",
    "SeoRecommendationPriority",
    "FieldOverride",
    "DEFAULT_IMMUTABLE_FIELDS",
    "MetadataField",
    "MetadataSection",
    "OpenGraphData",
    "OgImageField",
    "OverrideSource",
    "SchemaBlock",
    "SchemaIntelligenceSection",
    "SchemaValidationStatus",
    "TechnicalSeoSection",
]
