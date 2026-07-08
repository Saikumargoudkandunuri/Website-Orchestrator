"""Analytics Specialist Agent (M6 Build Phase F)."""
from __future__ import annotations

from agentic.agents.specialists.base import BaseSpecialistAgent


class AnalyticsAgent(BaseSpecialistAgent):
    """Specialist agent focusing on measurement, attribution, and KPI reasoning."""
    name = "analytics_agent"
    capabilities = ["analytics", "measurement", "traffic_diagnostics"]
    tools = ["seo_audit"]
    skills = ["kpi_mapping", "baseline_analysis", "ranking_drop_diagnosis"]
    cost = 1.0
    latency_ms = 110
    risk = "low"
    confidence = 0.83
    analysis = "Analytics baselines and anomaly context should guide mission prioritization."
    proposals = [{"action": "seo_audit", "risk_level": "low", "confidence": 0.82}]
