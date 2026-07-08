"""AnomalyDetection — z-score and IQR outlier detection (Phase 1).

Deterministic statistical anomaly detection — no AI calls.
"""

from __future__ import annotations

import math

from enterprise_intelligence.observation.models import AnomalyResult

__all__ = ["AnomalyDetection"]


class AnomalyDetection:
    """Detect anomalies in metric values using statistical methods.

    Supports z-score (default) and IQR methods.  Both are deterministic.
    """

    def __init__(self, z_threshold: float = 2.5, iqr_factor: float = 1.5) -> None:
        self._z_threshold = z_threshold
        self._iqr_factor = iqr_factor

    def detect_zscore(
        self,
        metric_name: str,
        value: float,
        historical_values: list[float],
    ) -> AnomalyResult:
        """Detect anomaly using z-score method."""
        if len(historical_values) < 3:
            return AnomalyResult(
                metric_name=metric_name,
                value=value,
                mean=0.0,
                std_dev=0.0,
                z_score=0.0,
                is_anomaly=False,
                method="z_score",
            )

        mean = sum(historical_values) / len(historical_values)
        variance = sum((v - mean) ** 2 for v in historical_values) / len(historical_values)
        std_dev = math.sqrt(variance) if variance > 0 else 0.0

        if std_dev == 0:
            z_score = 0.0
        else:
            z_score = (value - mean) / std_dev

        return AnomalyResult(
            metric_name=metric_name,
            value=value,
            mean=round(mean, 4),
            std_dev=round(std_dev, 4),
            z_score=round(z_score, 4),
            is_anomaly=abs(z_score) >= self._z_threshold,
            method="z_score",
        )

    def detect_iqr(
        self,
        metric_name: str,
        value: float,
        historical_values: list[float],
    ) -> AnomalyResult:
        """Detect anomaly using IQR method."""
        if len(historical_values) < 4:
            return AnomalyResult(
                metric_name=metric_name,
                value=value,
                mean=0.0,
                std_dev=0.0,
                z_score=0.0,
                is_anomaly=False,
                method="iqr",
            )

        sorted_vals = sorted(historical_values)
        n = len(sorted_vals)
        q1 = sorted_vals[n // 4]
        q3 = sorted_vals[(3 * n) // 4]
        iqr = q3 - q1

        lower = q1 - self._iqr_factor * iqr
        upper = q3 + self._iqr_factor * iqr

        mean = sum(historical_values) / n
        variance = sum((v - mean) ** 2 for v in historical_values) / n
        std_dev = math.sqrt(variance) if variance > 0 else 0.0
        z_score = (value - mean) / std_dev if std_dev > 0 else 0.0

        return AnomalyResult(
            metric_name=metric_name,
            value=value,
            mean=round(mean, 4),
            std_dev=round(std_dev, 4),
            z_score=round(z_score, 4),
            is_anomaly=value < lower or value > upper,
            method="iqr",
        )
