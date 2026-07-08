"""Decision Specialist Agent (M6 Build Phase F)."""
from __future__ import annotations

from agentic.agents.specialists.base import BaseSpecialistAgent


class DecisionAgent(BaseSpecialistAgent):
    """Specialist agent focusing on alternative weighting and approval reasoning."""
    name = "decision_agent"
    capabilities = ["decision", "risk_review", "alternative_selection"]
    tools = ["seo_audit", "content_generator"]
    skills = ["risk_scoring", "tradeoff_analysis", "approval_routing"]
    cost = 1.3
    latency_ms = 140
    risk = "medium"
    confidence = 0.85
    analysis = "Decision review recommends executing the highest-confidence approved proposals only."
    proposals = [{"action": "seo_audit", "risk_level": "low", "confidence": 0.86}]
