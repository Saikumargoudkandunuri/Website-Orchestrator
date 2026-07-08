"""Technical Specialist Agent (M6 Build Phase F)."""
from __future__ import annotations

from agentic.agents.specialists.base import BaseSpecialistAgent


class TechnicalAgent(BaseSpecialistAgent):
    """Specialist agent focusing on site performance and technical crawls."""
    name = "technical_agent"
    capabilities = ["technical_seo", "site_performance", "crawl_health"]
    tools = ["seo_audit"]
    skills = ["crawl_error_triage", "performance_review", "indexability_analysis"]
    cost = 1.1
    latency_ms = 130
    risk = "low"
    confidence = 0.84
    analysis = "Crawl, indexability, and performance checks are required before execution."
    proposals = [{"action": "seo_audit", "risk_level": "low", "confidence": 0.85}]
