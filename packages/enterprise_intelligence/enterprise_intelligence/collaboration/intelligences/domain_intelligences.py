"""Domain-scoped Intelligences (Phase 5).

Each Intelligence subclasses M6's BaseSpecialistAgent and represents a specific
governed business or technical domain capability view.
"""

from __future__ import annotations

from agentic.agents.specialists.base import BaseSpecialistAgent

__all__ = [
    "SeoIntelligence",
    "ContentIntelligence",
    "TechnicalIntelligence",
    "AnalyticsIntelligence",
    "GrowthIntelligence",
    "ReputationIntelligence",
    "AutomationIntelligence",
    "BusinessIntelligence",
]


class SeoIntelligence(BaseSpecialistAgent):
    name = "seo_intelligence"
    capabilities = ["seo", "technical_seo_audit", "keyword_research", "on_page_seo"]
    tools = ["seo_audit"]
    skills = ["ranking_diagnosis"]
    cost = 1.0
    latency_ms = 100
    confidence = 0.85
    analysis = "SEO Intelligence: Analysed rank positions and keyword targeting."
    proposals = [{"action": "seo_audit", "risk_level": "low", "confidence": 0.85}]


class ContentIntelligence(BaseSpecialistAgent):
    name = "content_intelligence"
    capabilities = ["content", "content_generation", "content_freshness"]
    tools = ["content_generator"]
    cost = 1.5
    latency_ms = 250
    confidence = 0.90
    analysis = "Content Intelligence: Evaluated stale pages and structured topics."
    proposals = [{"action": "content_generator", "risk_level": "medium", "confidence": 0.90}]


class TechnicalIntelligence(BaseSpecialistAgent):
    name = "technical_intelligence"
    capabilities = ["technical", "core_web_vitals", "speed_optimization"]
    cost = 1.2
    latency_ms = 150
    confidence = 0.88
    analysis = "Technical Intelligence: Identified Core Web Vitals regression."
    proposals = []


class AnalyticsIntelligence(BaseSpecialistAgent):
    name = "analytics_intelligence"
    capabilities = ["analytics", "conversion_rate", "traffic_metrics"]
    cost = 1.0
    latency_ms = 120
    confidence = 0.87
    analysis = "Analytics Intelligence: Evaluated conversion tracking and traffic drops."
    proposals = []


class GrowthIntelligence(BaseSpecialistAgent):
    name = "growth_intelligence"
    capabilities = ["growth", "opportunity_discovery", "outreach"]
    cost = 1.4
    latency_ms = 200
    confidence = 0.80
    analysis = "Growth Intelligence: Found domain authority and backlink opportunities."
    proposals = []


class ReputationIntelligence(BaseSpecialistAgent):
    name = "reputation_intelligence"
    capabilities = ["reputation", "reviews_sentiment", "brand_monitoring"]
    cost = 1.1
    latency_ms = 130
    confidence = 0.85
    analysis = "Reputation Intelligence: Sentiment analysis of user reviews."
    proposals = []


class AutomationIntelligence(BaseSpecialistAgent):
    name = "automation_intelligence"
    capabilities = ["automation", "rule_evaluation", "task_scheduling"]
    cost = 0.8
    latency_ms = 80
    confidence = 0.95
    analysis = "Automation Intelligence: Evaluated pipeline rules and triggers."
    proposals = []


class BusinessIntelligence(BaseSpecialistAgent):
    name = "business_intelligence"
    capabilities = ["business", "revenue_attribution", "roi_calculation"]
    cost = 1.3
    latency_ms = 180
    confidence = 0.92
    analysis = "Business Intelligence: Evaluated client campaigns and business values."
    proposals = []
