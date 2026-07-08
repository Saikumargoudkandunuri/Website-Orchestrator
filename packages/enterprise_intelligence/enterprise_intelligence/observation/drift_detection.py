"""DriftDetection — sliding-window mean comparison (Phase 1).

Deterministic statistical detection — no AI calls.  Compares the mean of
a recent window against a baseline window to detect significant drift.
"""

from __future__ import annotations

import math

from enterprise_intelligence.observation.models import DriftResult

__all__ = ["DriftDetection"]


class DriftDetection:
    """Detect significant drift in a metric time-series.

    Uses a two-window comparison: a *baseline* window (older data) and a
    *current* window (recent data).  Drift is significant if the absolute
    percentage change exceeds ``threshold_pct``.
    """

    def __init__(self, threshold_pct: float = 0.10) -> None:
        self._threshold = threshold_pct

    def detect(
        self,
        metric_name: str,
        baseline_values: list[float],
        current_values: list[float],
    ) -> DriftResult:
        """Compare baseline and current windows for drift."""
        if not baseline_values or not current_values:
            return DriftResult(
                metric_name=metric_name,
                baseline_mean=0.0,
                current_mean=0.0,
                drift_magnitude=0.0,
                drift_percentage=0.0,
                is_significant=False,
                window_size=0,
            )

        base_mean = sum(baseline_values) / len(baseline_values)
        curr_mean = sum(current_values) / len(current_values)
        magnitude = curr_mean - base_mean

        if base_mean != 0:
            pct = magnitude / abs(base_mean)
        else:
            pct = 0.0 if magnitude == 0 else float("inf")

        return DriftResult(
            metric_name=metric_name,
            baseline_mean=round(base_mean, 4),
            current_mean=round(curr_mean, 4),
            drift_magnitude=round(magnitude, 4),
            drift_percentage=round(pct, 4),
            is_significant=abs(pct) >= self._threshold,
            window_size=len(current_values),
        )
