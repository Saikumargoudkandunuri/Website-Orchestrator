"""Milestone 5 — Continuous Learning (item 8): post-publish measurement.

After a mission is applied, it is queued for verification against its own
real category metric (never a fabricated ranking/CTR/traffic number — those
require a connected Search Console/Analytics integration). Once the
observation window elapses, the next governed cycle measures the real delta
and feeds it back into ``strategy_stats`` via the existing
``record_strategy_outcome`` path — the same mechanism ``score_mission``
already reads from.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from api.cmo_memory import CMOMemoryStore, _VERIFICATION_WINDOW_SECONDS, extract_metric


def _snapshot(marketing_score: float, technical_health: float) -> dict:
    return {
        "marketing_score": marketing_score,
        "health_score": technical_health,
        "seo_score": technical_health,
        "components": {"technical_health": technical_health, "content_quality": 50,
                        "backlink_safety": 90, "ai_visibility": 40},
        "competitor_gaps": 0, "mission_count": 1, "mission_categories": [],
        "top_mission": None, "top_priority": 0,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }


def test_extract_metric_reads_top_level_and_component_metrics() -> None:
    snapshot = _snapshot(70, 60)
    assert extract_metric(snapshot, "marketing_score") == 70
    assert extract_metric(snapshot, "component.technical_health") == 60
    assert extract_metric(snapshot, "component.missing") == 0.0


def test_queue_mission_verification_records_real_baseline() -> None:
    store = CMOMemoryStore(repository=None)
    memory = store.load(tenant_id="t1", site="example.com")
    memory["latest_snapshot"] = _snapshot(70, 60)
    store.save(memory, tenant_id="t1", site="example.com")

    mission = {"id": "msn_1", "title": "Fix schema", "category": "technical_seo"}
    queued = store.queue_mission_verification(tenant_id="t1", site="example.com", mission=mission)

    pending = queued["pending_verifications"]
    assert len(pending) == 1
    assert pending[0]["mission_id"] == "msn_1"
    assert pending[0]["metric"] == "component.technical_health"
    assert pending[0]["baseline_value"] == 60


def test_resolve_pending_verifications_is_noop_before_window_elapses() -> None:
    store = CMOMemoryStore(repository=None)
    memory = store.load(tenant_id="t2", site="example.com")
    memory["latest_snapshot"] = _snapshot(70, 60)
    store.save(memory, tenant_id="t2", site="example.com")
    store.queue_mission_verification(
        tenant_id="t2", site="example.com", mission={"id": "msn_2", "title": "M", "category": "content"},
    )

    resolved = store.resolve_pending_verifications(tenant_id="t2", site="example.com")
    assert resolved == []
    memory_after = store.load(tenant_id="t2", site="example.com")
    assert len(memory_after["pending_verifications"]) == 1


def test_resolve_pending_verifications_measures_real_metric_delta_and_learns() -> None:
    store = CMOMemoryStore(repository=None)
    memory = store.load(tenant_id="t3", site="example.com")
    memory["latest_snapshot"] = _snapshot(70, 60)
    store.save(memory, tenant_id="t3", site="example.com")
    mission = {"id": "msn_3", "title": "Improve content", "category": "content"}
    queued = store.queue_mission_verification(tenant_id="t3", site="example.com", mission=mission)
    # Force the queued entry into the past so it's due.
    past = (datetime.now(timezone.utc) - timedelta(seconds=_VERIFICATION_WINDOW_SECONDS + 60)).isoformat()
    queued["pending_verifications"][0]["queued_at"] = past
    store.save(queued, tenant_id="t3", site="example.com")

    # Real content_quality improved from 50 -> 75 in the latest snapshot.
    memory2 = store.load(tenant_id="t3", site="example.com")
    memory2["latest_snapshot"] = _snapshot(80, 60)
    memory2["latest_snapshot"]["components"]["content_quality"] = 75
    store.save(memory2, tenant_id="t3", site="example.com")

    resolved = store.resolve_pending_verifications(tenant_id="t3", site="example.com")
    assert len(resolved) == 1
    result = resolved[0]
    assert result["mission_id"] == "msn_3"
    assert result["metric"] == "component.content_quality"
    assert result["baseline_value"] == 50
    assert result["current_value"] == 75
    assert result["metric_delta"] == 25.0
    assert result["successful"] is True

    memory_final = store.load(tenant_id="t3", site="example.com")
    assert memory_final["pending_verifications"] == []
    stats = memory_final["strategy_stats"]["content"]
    assert stats["successful"] == 1
    assert stats["attempts"] == 1


def test_resolve_pending_verifications_records_failure_on_negative_delta() -> None:
    store = CMOMemoryStore(repository=None)
    memory = store.load(tenant_id="t4", site="example.com")
    memory["latest_snapshot"] = _snapshot(70, 60)
    store.save(memory, tenant_id="t4", site="example.com")
    mission = {"id": "msn_4", "title": "Backlink cleanup", "category": "backlinks"}
    queued = store.queue_mission_verification(tenant_id="t4", site="example.com", mission=mission)
    past = (datetime.now(timezone.utc) - timedelta(seconds=_VERIFICATION_WINDOW_SECONDS + 60)).isoformat()
    queued["pending_verifications"][0]["queued_at"] = past
    store.save(queued, tenant_id="t4", site="example.com")

    memory2 = store.load(tenant_id="t4", site="example.com")
    memory2["latest_snapshot"] = _snapshot(70, 60)
    memory2["latest_snapshot"]["components"]["backlink_safety"] = 70  # declined from 90
    store.save(memory2, tenant_id="t4", site="example.com")

    resolved = store.resolve_pending_verifications(tenant_id="t4", site="example.com")
    assert resolved[0]["successful"] is False
    assert resolved[0]["metric_delta"] == -20.0
    memory_final = store.load(tenant_id="t4", site="example.com")
    assert memory_final["strategy_stats"]["backlinks"]["failed"] == 1
