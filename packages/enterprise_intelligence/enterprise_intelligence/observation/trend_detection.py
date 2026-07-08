"""TrendDetection — linear regression over time-series windows (Phase 1).

Deterministic statistical trend detection — no AI calls.
"""

from __future__ import annotations

import math

from enterprise_intelligence.observation.models import TrendResult

__all__ = ["TrendDetection"]


class TrendDetection:
    """Detect directional trends in a metric time-series.

    Uses simple linear regression (least squares) over a sequence of values
    assumed to be equally spaced in time.  A trend is significant if the
    R² exceeds ``min_r_squared`` and the slope exceeds ``min_slope``.
    """

    def __init__(
        self,
        min_r_squared: float = 0.5,
        min_slope: float = 0.01,
    ) -> None:
        self._min_r2 = min_r_squared
        self._min_slope = min_slope

    def detect(self, metric_name: str, values: list[float]) -> TrendResult:
        """Fit a linear trend and report direction/significance."""
        n = len(values)
        if n < 3:
            return TrendResult(
                metric_name=metric_name,
                slope=0.0,
                r_squared=0.0,
                direction="stable",
                is_significant=False,
            )

        # Simple linear regression: y = slope * x + intercept
        x_vals = list(range(n))
        x_mean = sum(x_vals) / n
        y_mean = sum(values) / n

        numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_vals, values))
        denominator = sum((x - x_mean) ** 2 for x in x_vals)

        if denominator == 0:
            slope = 0.0
        else:
            slope = numerator / denominator

        # R²
        ss_res = sum((y - (slope * x + (y_mean - slope * x_mean))) ** 2 for x, y in zip(x_vals, values))
        ss_tot = sum((y - y_mean) ** 2 for y in values)
        r_squared = 1.0 - (ss_res / ss_tot) if ss_tot != 0 else 0.0
        r_squared = max(0.0, min(1.0, r_squared))

        if abs(slope) >= self._min_slope and r_squared >= self._min_r2:
            direction = "up" if slope > 0 else "down"
            significant = True
        else:
            direction = "stable"
            significant = False

        return TrendResult(
            metric_name=metric_name,
            slope=round(slope, 6),
            r_squared=round(r_squared, 4),
            direction=direction,
            is_significant=significant,
        )
