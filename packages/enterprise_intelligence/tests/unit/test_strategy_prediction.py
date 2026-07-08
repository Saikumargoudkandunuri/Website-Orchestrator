"""Phase 6 — Strategic and Predictive Intelligence unit and property tests.

Tests cover: ForecastEngine predictions, ScenarioPlanner isolation (what-if),
threat detection, resource cost optimization advice, and a Hypothesis property-based
test verifying that forecast confidence intervals widen over time.
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone
from hypothesis import given, settings, strategies as st

from agentic.goal.models import Goal, StructuredObjective, GoalContext, GoalStatus
from enterprise_intelligence.knowledge.enterprise_graph import EnterpriseGraph
from enterprise_intelligence.knowledge.models import EnterpriseNode, ProvenanceRecord
from enterprise_intelligence.strategy_prediction.forecast import ForecastEngine, ForecastResult
from enterprise_intelligence.strategy_prediction.strategy_engine import (
    ScenarioPlanner,
    ThreatDetector,
    OpportunityDiscoverer,
    StrategyEngine,
    RoadmapGenerator,
    ResourceOptimizer,
)


class TestForecastEngine:
    def test_forecast_values_generated(self):
        engine = ForecastEngine()
        history = [10.0, 12.0, 11.0, 13.0, 15.0]
        
        result = engine.generate_forecast(
            category="traffic",
            metric_name="organic_traffic",
            historical_values=history,
            horizon_steps=3,
        )
        assert result.category == "traffic"
        assert len(result.forecasted_values) == 3
        assert len(result.lower_bound) == 3
        assert len(result.upper_bound) == 3

    # Hypothesis property-based test
    @given(st.lists(st.floats(min_value=1.0, max_value=1000.0), min_size=5, max_size=50))
    @settings(max_examples=100)
    def test_forecast_confidence_intervals_widen_property(self, history):
        """Property-based test: the width of the confidence interval (upper_bound - lower_bound)
        must widen strictly (or remain equal) as the forecasting horizon extends.
        """
        engine = ForecastEngine()
        result = engine.generate_forecast(
            category="traffic",
            metric_name="organic_traffic",
            historical_values=history,
            horizon_steps=5,
        )
        
        widths = [
            (up - low)
            for up, low in zip(result.upper_bound, result.lower_bound)
        ]
        
        # Check that widths of intervals are strictly increasing or equal as time goes on
        for i in range(1, len(widths)):
            assert widths[i] >= widths[i - 1], f"Interval narrowed at step {i}: {widths[i]} < {widths[i - 1]}"


class TestScenarioPlanner:
    def test_what_if_is_isolated(self):
        forecast_engine = ForecastEngine()
        planner = ScenarioPlanner(forecast_engine)
        
        base_metrics = {"traffic": [100.0, 110.0, 120.0]}
        perturbations = {"traffic": -0.20}  # 20% drop
        
        scenario_res = planner.run_what_if_scenario("Drop 20%", base_metrics, perturbations)
        assert scenario_res.scenario_name == "Drop 20%"
        assert scenario_res.is_hypothetical is True
        
        # Base metric values are not modified in base_metrics dict
        assert base_metrics["traffic"] == [100.0, 110.0, 120.0]
        
        # Impact forecast contains traffic
        assert "traffic" in scenario_res.impact_forecasts
        # Re-forecast values should reflect the 20% drop (e.g. baseline is ~110, drop makes it ~88, so prediction should be lower)
        base_forecast = forecast_engine.generate_forecast("test", "traffic", base_metrics["traffic"])
        assert scenario_res.impact_forecasts["traffic"].forecasted_values[0] < base_forecast.forecasted_values[0]


class TestStrategyReasoning:
    def test_threat_detection(self):
        detector = ThreatDetector()
        
        # Normal forecast
        f_normal = ForecastResult(
            category="traffic",
            target_metric="traffic",
            forecasted_values=[100.0, 100.0, 100.0],
            lower_bound=[90, 80, 70],
            upper_bound=[110, 120, 130],
        )
        
        # Threat forecast (severe downward trend)
        f_decay = ForecastResult(
            category="traffic",
            target_metric="traffic",
            forecasted_values=[100.0, 70.0, 50.0],
            lower_bound=[90, 60, 40],
            upper_bound=[110, 80, 60],
        )
        
        threats = detector.analyze_threats([f_normal, f_decay])
        assert len(threats) == 1
        assert threats[0]["metric"] == "traffic"
        assert threats[0]["type"] == "performance_decay"

    def test_opportunity_discovery_and_roadmap(self):
        discoverer = OpportunityDiscoverer()
        generator = RoadmapGenerator()
        
        prov = ProvenanceRecord(source_engine="test", source_operation="test", evidence_refs=[])
        node = EnterpriseNode(
            id="camp-1",
            node_type="campaign",
            label="Product Launch",
            site_id="s1",
            tenant_id="t1",
            provenance=prov,
        )
        graph = EnterpriseGraph(tenant_id="t1", site_id="s1", enterprise_nodes=[node])
        
        opportunities = discoverer.find_opportunities(graph)
        assert len(opportunities) == 1
        assert opportunities[0]["type"] == "campaign_optimization"
        
        roadmap = generator.generate_roadmap(graph, opportunities)
        assert len(roadmap) == 1
        assert roadmap[0].raw_objective == "Expand keyword targeting for campaign: Product Launch"
        assert roadmap[0].status == GoalStatus.DRAFT

    def test_resource_optimizer(self):
        optimizer = ResourceOptimizer()
        
        # Within budget
        rec1 = optimizer.generate_recommendations([10.0, 15.0, 12.0], budget_limit=50.0)
        assert not rec1["needs_optimization"]
        
        # Out of budget
        rec2 = optimizer.generate_recommendations([20.0, 25.0, 22.0], budget_limit=50.0)
        assert rec2["needs_optimization"]
        assert "caching" in rec2["recommendation"]
