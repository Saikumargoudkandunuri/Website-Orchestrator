"""Knowledge Specialist Agent (M6 Build Phase F)."""
from __future__ import annotations

from agentic.agents.specialists.base import BaseSpecialistAgent


class KnowledgeAgent(BaseSpecialistAgent):
    """Specialist agent focusing on enterprise knowledge and evidence reasoning."""
    name = "knowledge_agent"
    capabilities = ["knowledge", "evidence_synthesis", "semantic_context"]
    tools = ["seo_audit"]
    skills = ["knowledge_retrieval", "evidence_validation", "context_synthesis"]
    cost = 0.8
    latency_ms = 95
    risk = "low"
    confidence = 0.8
    analysis = "Knowledge context should be attached as evidence before runtime execution."
    proposals = [{"action": "seo_audit", "risk_level": "low", "confidence": 0.79}]
