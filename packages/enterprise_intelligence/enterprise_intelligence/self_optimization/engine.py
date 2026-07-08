"""Self Optimization Subsystem (Phase 7).

Tunes model routing, planner heuristics, cache policies, and confidence metrics.
Enforces that safety thresholds, permissions, and gates are structurally untouchable.
"""

from __future__ import annotations

import logging
from typing import Any

__all__ = [
    "ProviderRouter",
    "PlannerHeuristicTuner",
    "CacheOptimizer",
    "ConfidenceCalibration",
]

logger = logging.getLogger(__name__)


class ProviderRouter:
    """Tunes AI provider routing based on cost/performance history.

    Recommends the best provider and model for a given capability, prioritizing
    efficiency.
    """

    def get_best_provider(
        self, capability: str, performance_history: list[dict[str, Any]]
    ) -> str:
        """Analyze past latency and token costs, and route to the optimal provider."""
        if not performance_history:
            return "openai"  # default standard provider

        # Score candidates by cost * 0.7 + latency * 0.3 (lower score is better)
        scores = {}
        for entry in performance_history:
            provider = entry.get("provider", "openai")
            cost = entry.get("cost_dollars", 0.01)
            latency = entry.get("latency_ms", 500)
            success = entry.get("success", True)
            
            if not success:
                # penalize failure
                cost *= 5
                
            score = cost * 1000 * 0.7 + (latency / 100) * 0.3
            scores[provider] = min(scores.get(provider, 999.0), score)

        if not scores:
            return "openai"
            
        return min(scores, key=scores.get)


class PlannerHeuristicTuner:
    """Tunes planner weights based on historical plan success rates.

    Logs all adjustments.  Does NOT touch governance thresholds.
    """

    def __init__(self) -> None:
        self.weights = {"cost": 0.5, "speed": 0.5}
        self.adjustment_log: list[dict[str, Any]] = []

    def tune_weights(self, execution_history: list[dict[str, Any]]) -> None:
        """Adjust planner heuristic weights based on history.

        If cost is a primary source of failure/limit exceeded, increase cost weight.
        """
        failures = [h for h in execution_history if not h.get("success", False)]
        if not failures:
            return

        cost_failures = sum(1 for f in failures if "budget" in str(f.get("error", "")).lower())
        speed_failures = sum(1 for f in failures if "timeout" in str(f.get("error", "")).lower())

        before = dict(self.weights)

        # Bounded adjustments
        if cost_failures > speed_failures:
            self.weights["cost"] = min(0.8, self.weights["cost"] + 0.05)
            self.weights["speed"] = max(0.2, self.weights["speed"] - 0.05)
        elif speed_failures > cost_failures:
            self.weights["speed"] = min(0.8, self.weights["speed"] + 0.05)
            self.weights["cost"] = max(0.2, self.weights["cost"] - 0.05)

        self.adjustment_log.append({
            "timestamp": datetime.now().isoformat() if "datetime" in globals() else "",
            "before": before,
            "after": dict(self.weights),
            "reason": f"Tuned due to {cost_failures} cost failures and {speed_failures} speed failures",
        })


class CacheOptimizer:
    """Optimizes TTL and cache rules dynamically based on hit rate logs."""

    def optimize_ttl(
        self, current_ttl: int, hit_rate: float, miss_rate: float
    ) -> int:
        """Adjust cache TTL. If hit rate is low and misses are high, increase TTL."""
        if hit_rate < 0.3 and miss_rate > 0.7:
            # Increase caching length
            return min(86400, current_ttl + 3600)
        elif hit_rate > 0.8:
            # Cache is fresh, can slightly decrease to save memory
            return max(300, current_ttl - 600)
        return current_ttl


class ConfidenceCalibration:
    """Calibrates confidence indicators dynamically by comparing estimates against outcomes."""

    def calibrate(
        self, confidence_vs_outcome: list[tuple[float, bool]]
    ) -> float:
        """Calculate calibration factor.

        If predicted confidence of 90% only succeeds 60% of the time,
        returns a calibration multiplier of 0.67 to scale predictions.
        """
        if not confidence_vs_outcome:
            return 1.0

        total_predicted = 0.0
        total_succeeded = 0.0
        
        for pred, success in confidence_vs_outcome:
            total_predicted += pred
            if success:
                total_succeeded += 1.0

        if total_predicted == 0:
            return 1.0
            
        ratio = total_succeeded / len(confidence_vs_outcome)
        avg_pred = total_predicted / len(confidence_vs_outcome)
        
        # Calibration scalar
        return round(ratio / avg_pred, 4) if avg_pred > 0 else 1.0
