"""Reusable, versioned prompt templates — one per AI capability (§6)."""

from intelligence.prompts.accessibility_prompt import AccessibilityPrompt
from intelligence.prompts.base_prompt_template import (
    BasePromptTemplate,
    PromptContext,
)
from intelligence.prompts.content_analysis_prompt import ContentAnalysisPrompt
from intelligence.prompts.content_expansion_prompt import ContentExpansionPrompt
from intelligence.prompts.content_rewrite_prompt import ContentRewritePrompt
from intelligence.prompts.content_score_narrative_prompt import ContentScoreNarrativePrompt
from intelligence.prompts.faq_generator_prompt import FaqGeneratorPrompt
from intelligence.prompts.image_alt_prompt import ImageAltPrompt
from intelligence.prompts.internal_linking_prompt import InternalLinkingPrompt
from intelligence.prompts.keyword_analysis_prompt import KeywordAnalysisPrompt
from intelligence.prompts.keyword_gap_reasoning_prompt import KeywordGapReasoningPrompt
from intelligence.prompts.meta_generator_prompt import MetaGeneratorPrompt
from intelligence.prompts.opportunity_justification_prompt import OpportunityJustificationPrompt
from intelligence.prompts.recommendation_synthesis_prompt import RecommendationSynthesisPrompt
from intelligence.prompts.schema_generator_prompt import SchemaGeneratorPrompt
from intelligence.prompts.seo_audit_prompt import SeoAuditPrompt
from intelligence.prompts.slug_generator_prompt import SlugGeneratorPrompt
from intelligence.prompts.technical_audit_prompt import TechnicalAuditPrompt
from intelligence.prompts.technical_seo_explanation_prompt import TechnicalSeoExplanationPrompt
from intelligence.prompts.title_generator_prompt import TitleGeneratorPrompt

#: Every concrete prompt template class, in a stable order.
ALL_PROMPT_TEMPLATES: tuple[type[BasePromptTemplate], ...] = (
    SeoAuditPrompt,
    ContentAnalysisPrompt,
    KeywordAnalysisPrompt,
    SlugGeneratorPrompt,
    MetaGeneratorPrompt,
    TitleGeneratorPrompt,
    FaqGeneratorPrompt,
    SchemaGeneratorPrompt,
    AccessibilityPrompt,
    ImageAltPrompt,
    InternalLinkingPrompt,
    ContentRewritePrompt,
    ContentExpansionPrompt,
    TechnicalAuditPrompt,
    # Milestone 3 engine-specific prompts
    TechnicalSeoExplanationPrompt,
    ContentScoreNarrativePrompt,
    OpportunityJustificationPrompt,
    RecommendationSynthesisPrompt,
    KeywordGapReasoningPrompt,
)

__all__ = [
    "BasePromptTemplate",
    "PromptContext",
    "ALL_PROMPT_TEMPLATES",
    "AccessibilityPrompt",
    "ContentAnalysisPrompt",
    "ContentExpansionPrompt",
    "ContentRewritePrompt",
    "ContentScoreNarrativePrompt",
    "FaqGeneratorPrompt",
    "ImageAltPrompt",
    "InternalLinkingPrompt",
    "KeywordAnalysisPrompt",
    "KeywordGapReasoningPrompt",
    "MetaGeneratorPrompt",
    "OpportunityJustificationPrompt",
    "RecommendationSynthesisPrompt",
    "SchemaGeneratorPrompt",
    "SeoAuditPrompt",
    "SlugGeneratorPrompt",
    "TechnicalAuditPrompt",
    "TechnicalSeoExplanationPrompt",
    "TitleGeneratorPrompt",
]
