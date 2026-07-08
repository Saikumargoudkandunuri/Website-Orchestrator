"""Confidence calibration engine (M6 Build Phase E)."""
from __future__ import annotations

from typing import Any
from agentic.reflection.repositories import ConfidenceCalibrationRepository


class ConfidenceEngine:
    """Continuously calibrates predicted success likelihood against actual outcomes."""
    
    def __init__(self, repo: ConfidenceCalibrationRepository) -> None:
        self._repo = repo
        
    def calibrate_category(
        self,
        tenant_id: str,
        category: str,
        predicted_success: float,
        actual_success: float,
    ) -> dict[str, Any]:
        """
        Compare predicted success rates with actual runs, updating calibration factors.
        """
        existing = self._repo.get_calibration(tenant_id, category)
        if existing:
            # Simple rolling average calibration
            p_avg = (existing["predicted_avg"] + predicted_success) / 2.0
            a_avg = (existing["actual_avg"] + actual_success) / 2.0
        else:
            p_avg = predicted_success
            a_avg = actual_success
            
        # Calibration factor: ratio of actual vs predicted success
        calibration_factor = a_avg / p_avg if p_avg > 0 else 1.0
        # Restrict factor bounds to avoid division by zero or extreme outliers
        calibration_factor = max(0.1, min(1.0, calibration_factor))
        
        self._repo.save_calibration(
            tenant_id=tenant_id,
            category=category,
            predicted_avg=p_avg,
            actual_avg=a_avg,
            calibration_factor=calibration_factor,
        )
        
        return {
            "category": category,
            "predicted_avg": p_avg,
            "actual_avg": a_avg,
            "calibration_factor": calibration_factor,
        }
        
    def get_calibration_factor(self, tenant_id: str, category: str) -> float:
        existing = self._repo.get_calibration(tenant_id, category)
        if existing:
            return float(existing.get("calibration_factor", 1.0))
        return 1.0
