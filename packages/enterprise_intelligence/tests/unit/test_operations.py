"""Phase 8 — Enterprise Operations unit and safety tests.

Tests cover: DistributedScheduler wrapper, HADRManager drills, ReplayTool trace
reconstruction, and adversarial replay safety boundary checks.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
import pytest

from enterprise_intelligence.observation.models import ObservationEvent, EventCategory
from enterprise_intelligence.operations.engine import DistributedScheduler, HADRManager, ReplayTool


class MockPlatformScheduler:
    def trigger_schedule(self, tenant_id: str, site_id: str, task_id: str) -> str:
        return f"triggered_{task_id}"


class MockEventStore:
    def __init__(self, events):
        self.events = events

    def list_events(self, tenant_id):
        return [e for e in self.events if e.tenant_id == tenant_id]


class TestOperations:
    def test_distributed_scheduler(self):
        platform = MockPlatformScheduler()
        dist = DistributedScheduler(platform)
        res = dist.submit_task("t1", "s1", "crawl_all")
        assert res == "triggered_crawl_all"

    def test_hadr_manager(self):
        mgr = HADRManager()
        status = mgr.verify_failover_status()
        assert status["failover_ready"] is True
        assert status["database_connected"] is True

    def test_replay_tool(self):
        e1 = ObservationEvent(
            tenant_id="t1",
            site_id="s1",
            category=EventCategory.RANKING,
            source_engine="test",
            source_ref="trace-abc",
            title="e1",
            description="desc",
            created_at=datetime.now(timezone.utc),
        )
        e2 = ObservationEvent(
            tenant_id="t1",
            site_id="s1",
            category=EventCategory.TECHNICAL,
            source_engine="test",
            source_ref="trace-abc",
            title="e2",
            description="desc",
            created_at=datetime.now(timezone.utc),
        )
        
        store = MockEventStore([e1, e2])
        tool = ReplayTool(store)
        
        seq = tool.replay_decision_path("t1", "trace-abc")
        assert len(seq) == 2
        assert seq[0].title == "e1"
        assert seq[1].title == "e2"


class TestReplaySafetyBoundary:
    """Safety checks for Phase 8.

    Enforce that ReplayTool does not contain imports or hooks that could trigger
    live governed actions (no Executor, runtime execution, or write endpoints).
    """

    def test_replay_is_strictly_read_only(self):
        ops_file = os.path.join(
            os.path.dirname(__file__),
            os.pardir, os.pardir,
            "enterprise_intelligence", "operations", "engine.py"
        )
        ops_file = os.path.normpath(ops_file)
        
        with open(ops_file, "r", encoding="utf-8") as f:
            source = f.read()

        forbidden_terms = ["Executor", "AgentRuntime", "wp_publish", "execute_node", "GovernanceGate"]
        violations = [term for term in forbidden_terms if term in source]
        assert not violations, f"ReplayTool safety violation: references live runtime components {violations}"
