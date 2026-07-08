"""Content Specialist Agent (M6 Build Phase F)."""
from __future__ import annotations

from agentic.agents.specialists.base import BaseSpecialistAgent


class ContentAgent(BaseSpecialistAgent):
    """Specialist agent focusing on content generation and optimization reasoning."""
    name = "content_agent"
    capabilities = ["content", "content_generation", "content_optimization"]
    tools = ["content_generator"]
    skills = ["keyword_mapping", "brief_generation", "content_gap_analysis"]
    cost = 2.0
    latency_ms = 180
    risk = "medium"
    confidence = 0.82
    analysis = "Content optimization is needed for high-intent organic traffic opportunities."
    proposals = [{"action": "content_generator", "risk_level": "medium", "confidence": 0.84}]
