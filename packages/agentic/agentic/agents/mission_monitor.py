"""Mission Monitor for reporting real-time progress (M6 Build Phase F)."""
from __future__ import annotations

import uuid

from agentic.agents.repositories import MissionMetricsRepository
from agentic.agents.types import JsonObject


class MissionMonitor:
    """Persists structured mission telemetry without mutating mission state."""

    def __init__(self, metrics_repo: MissionMetricsRepository) -> None:
        self._metrics_repo = metrics_repo

    def log_mission_start(self, tenant_id: str, mission_id: str, objective: str) -> None:
        self._metrics_repo.save_metric(
            tenant_id,
            mission_id,
            f"metric_{uuid.uuid4().hex}",
            {"event": "mission_started", "objective": objective},
        )

    def log_mission_progress(self, tenant_id: str, mission_id: str, state: str, details: JsonObject) -> None:
        payload: JsonObject = {"event": "mission_progress", "state": state, "details": details}
        self._metrics_repo.save_metric(tenant_id, mission_id, f"metric_{uuid.uuid4().hex}", payload)
