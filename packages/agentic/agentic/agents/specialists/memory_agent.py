"""Memory Specialist Agent (M6 Build Phase F)."""
from __future__ import annotations

from agentic.agents.specialists.base import BaseSpecialistAgent


class MemoryAgent(BaseSpecialistAgent):
    """Specialist agent focusing on memory-informed reasoning without direct memory mutation."""
    name = "memory_agent"
    capabilities = ["memory", "experience_recall", "lesson_application"]
    tools = ["seo_audit"]
    skills = ["episodic_recall", "reflection_lookup", "workflow_reuse"]
    cost = 0.7
    latency_ms = 90
    risk = "low"
    confidence = 0.78
    analysis = "Relevant prior experiences should inform the runtime plan but remain immutable to agents."
    proposals = [{"action": "seo_audit", "risk_level": "low", "confidence": 0.77}]
