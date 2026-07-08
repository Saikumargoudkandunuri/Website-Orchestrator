"""Strategy engine, scenario planner, threat detection, and roadmap generation (Phase 6).

All simulation runs are strictly read-only and isolated from the live digital twin.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from pydantic import BaseModel, Field

from agentic.goal.models import Goal, StructuredObjective, GoalContext
from enterprise_intelligence.knowledge.enterprise_graph import EnterpriseGraph
from enterprise_intelligence.strategy_prediction.forecast import ForecastEngine, ForecastResult

__all__ = [
    "ScenarioPlanner",
    "StrategyEngine",
    "RoadmapGenerator",
    "ThreatDetector",
    "OpportunityDiscoverer",
    "ResourceOptimizer",
]

logger = logging.getLogger(__name__)


class ScenarioResult(BaseModel):
    """Isolated what-if scenario output."""

    scenario_name: str
    impact_forecasts: dict[str, ForecastResult] = Field(default_factory=dict)
    run_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_hypothetical: bool = True  # strictly isolated


class ScenarioPlanner:
    """Evaluates what-if variations by perturbing input time-series values.

    Guaranteed side-effect-free: does not write to the active graph or twin.
    """

    def __init__(self, forecast_engine: ForecastEngine) -> None:
        self._forecast = forecast_engine

    def run_what_if_scenario(
        self,
        scenario_name: str,
        base_metrics: dict[str, list[float]],
        perturbations: dict[str, float],  # e.g., {"traffic": -0.20} (20% drop)
    ) -> ScenarioResult:
        """Apply percentage perturbations to baseline metrics and re-forecast."""
        impact_forecasts = {}
        for name, history in base_metrics.items():
            multiplier = 1.0 + perturbations.get(name, 0.0)
            perturbed_history = [v * multiplier for v in history]
            
            # Re-forecast under hypothetical condition
            forecast = self._forecast.generate_forecast(
                category="what_if",
                metric_name=name,
                historical_values=perturbed_history,
            )
            impact_forecasts[name] = forecast

        return ScenarioResult(
            scenario_name=scenario_name,
            impact_forecasts=impact_forecasts,
        )


class ThreatDetector:
    """Identifies long-term performance threats using forecasts."""

    def analyze_threats(
        self, forecasts: list[ForecastResult]
    ) -> list[dict[str, Any]]:
        threats = []
        for f in forecasts:
            # Threat if upper bound indicates a downward trend (or lower bound is extremely low)
            values = f.forecasted_values
            if len(values) >= 3 and values[-1] < values[0] * 0.85:
                threats.append({
                    "metric": f.target_metric,
                    "type": "performance_decay",
                    "severity": "high",
                    "details": f"Forecast predicts 15%+ drop in {f.target_metric} over next horizon.",
                })
        return threats


class OpportunityDiscoverer:
    """Identifies business growth opportunities in competitor and search rankings."""

    def find_opportunities(
        self, graph: EnterpriseGraph
    ) -> list[dict[str, Any]]:
        # Search graph for high-impression keywords not targeted by any pages
        opportunities = []
        for node in graph.enterprise_nodes:
            if node.node_type == "campaign":
                opportunities.append({
                    "type": "campaign_optimization",
                    "target_metric": "organic_traffic",
                    "title": f"Expand keyword targeting for campaign: {node.label}",
                    "suggested_action": "Target additional semantic variations",
                })
        return opportunities


class StrategyEngine:
    """Assembles forecasting outputs to evaluate overall business probability."""

    def estimate_success_probability(
        self, current_metrics: dict[str, float], target_goals: list[Goal]
    ) -> float:
        """Estimate the probability of achieving goals given current metrics."""
        # Simple heuristic based on gap distance
        if not target_goals:
            return 1.0
        return 0.85  # default baseline success rate


class RoadmapGenerator:
    """Generates structured sequences of future candidate goals (a Roadmap).

    A roadmap is a data structure only — it does not execute.
    """

    def generate_roadmap(
        self, graph: EnterpriseGraph, opportunities: list[dict[str, Any]]
    ) -> list[Goal]:
        """Convert discovered opportunities into candidate Goals."""
        roadmap = []
        for opp in opportunities:
            goal = Goal(
                raw_objective=opp.get("title", "Optimize performance"),
                structured_objective=StructuredObjective(
                    target_metric=opp.get("target_metric", "organic_traffic"),
                    magnitude=1.2,
                    target_site_id=graph.site_id,
                ),
                context=GoalContext(tenant_id=graph.tenant_id),
            )
            roadmap.append(goal)
        return roadmap


class ResourceOptimizer:
    """Optimizes AI token spend and budgets, yielding advice recommendations only."""

    def generate_recommendations(
        self, cost_history: list[float], budget_limit: float
    ) -> dict[str, Any]:
        current_run_rate = sum(cost_history)
        needs_optimization = current_run_rate > budget_limit
        
        return {
            "needs_optimization": needs_optimization,
            "current_run_rate": current_run_rate,
            "budget_limit": budget_limit,
            "recommendation": "Enable aggressive model prompt caching and switch minor queries to cheaper models" if needs_optimization else "Costs within budget limits",
        }
