"""Research Specialist Agent (M6 Build Phase F)."""
from __future__ import annotations

from agentic.agents.specialists.base import BaseSpecialistAgent


class ResearchAgent(BaseSpecialistAgent):
    """Specialist agent focusing on market and search research reasoning."""
    name = "research_agent"
    capabilities = ["research", "market_research", "keyword_research"]
    tools = ["seo_audit", "content_generator"]
    skills = ["keyword_discovery", "competitor_review", "search_intent_mapping"]
    cost = 1.4
    latency_ms = 170
    risk = "medium"
    confidence = 0.8
    analysis = "Research indicates that keyword and competitor evidence should shape mission execution."
    proposals = [{"action": "content_generator", "risk_level": "medium", "confidence": 0.81}]
