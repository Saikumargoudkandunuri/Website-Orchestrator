"""Phase 7 — Self Optimization unit tests.

Tests cover: ProviderRouter routing optimization, PlannerHeuristicTuner adjustments,
CacheOptimizer TTL limits, ConfidenceCalibration scoring, and structural safety
checks excluding governance models from self-modification.
"""

from __future__ import annotations

import os
import pytest

from enterprise_intelligence.self_optimization.engine import (
    ProviderRouter,
    PlannerHeuristicTuner,
    CacheOptimizer,
    ConfidenceCalibration,
)


class TestSelfOptimization:
    def test_provider_router(self):
        router = ProviderRouter()
        
        # Test case: provider_cheap is slow but very cheap, provider_fast is fast but expensive
        history = [
            {"provider": "provider_cheap", "cost_dollars": 0.001, "latency_ms": 900, "success": True},
            {"provider": "provider_fast", "cost_dollars": 0.05, "latency_ms": 100, "success": True},
        ]
        
        best = router.get_best_provider("content_generation", history)
        # Cost * 0.7 + latency * 0.3
        # provider_cheap score: 0.001 * 1000 * 0.7 + 9 * 0.3 = 0.7 + 2.7 = 3.4
        # provider_fast score: 0.05 * 1000 * 0.7 + 1 * 0.3 = 35 + 0.3 = 35.3
        # Should pick provider_cheap
        assert best == "provider_cheap"

    def test_planner_heuristic_tuner(self):
        tuner = PlannerHeuristicTuner()
        
        # Case: Cost failures
        history = [
            {"success": False, "error": "budget limit exceeded"},
            {"success": False, "error": "budget limit exceeded"},
        ]
        
        tuner.tune_weights(history)
        assert tuner.weights["cost"] > 0.5
        assert tuner.weights["speed"] < 0.5
        assert len(tuner.adjustment_log) == 1

    def test_cache_optimizer_ttl(self):
        opt = CacheOptimizer()
        
        # Hit rate low, miss rate high -> increase TTL
        ttl1 = opt.optimize_ttl(current_ttl=3600, hit_rate=0.1, miss_rate=0.9)
        assert ttl1 > 3600

        # Hit rate high -> decrease TTL slightly
        ttl2 = opt.optimize_ttl(current_ttl=3600, hit_rate=0.9, miss_rate=0.1)
        assert ttl2 < 3600

    def test_confidence_calibration(self):
        cal = ConfidenceCalibration()
        
        # Predicted confidence of 90% but only succeeded 60% of the time
        history = [(0.9, True), (0.9, False), (0.9, True)]
        scalar = cal.calibrate(history)
        # Average predicted: 0.9, actual success rate: 2/3 = 0.6666
        # scalar should be 0.6666 / 0.9 = 0.7407
        assert scalar < 1.0


class TestSelfOptimizationSafety:
    """Safety/Governance structural checks for Phase 7.

    Enforce that Self Optimization contains ZERO references to GoalConstraints,
    requires_approval, or GovernanceGate to prevent modifying safety permissions.
    """

    def test_no_governance_writes_in_optimization(self):
        opt_file = os.path.join(
            os.path.dirname(__file__),
            os.pardir, os.pardir,
            "enterprise_intelligence", "self_optimization", "engine.py"
        )
        opt_file = os.path.normpath(opt_file)
        
        with open(opt_file, "r", encoding="utf-8") as f:
            source = f.read()

        forbidden_terms = ["GoalConstraints", "requires_approval", "GovernanceGate", "RBAC"]
        violations = [term for term in forbidden_terms if term in source]
        assert not violations, f"SelfOptimization safety violation: references governance/RBAC variables {violations}"
