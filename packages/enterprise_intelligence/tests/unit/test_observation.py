"""Phase 1 — Continuous Observation unit tests.

Tests cover: models, EventBus, EventClassifier, EventPrioritizer,
EventCorrelationEngine, DriftDetection, TrendDetection, KpiMonitoring,
AnomalyDetection, PredictiveAlerts, source adapters, and structural
governance-bypass verification.
"""

from __future__ import annotations

import ast
import inspect
import os
import textwrap
from datetime import datetime, timedelta, timezone

import pytest

from enterprise_intelligence.observation.models import (
    AnomalyResult,
    CorrelatedEventGroup,
    DriftResult,
    EventCategory,
    EventSeverity,
    KpiAlert,
    ObservationEvent,
    TrendResult,
)
from enterprise_intelligence.observation.event_bus import EventBus
from enterprise_intelligence.observation.classifier import EventClassifier
from enterprise_intelligence.observation.prioritizer import EventPrioritizer
from enterprise_intelligence.observation.correlation_engine import EventCorrelationEngine
from enterprise_intelligence.observation.drift_detection import DriftDetection
from enterprise_intelligence.observation.trend_detection import TrendDetection
from enterprise_intelligence.observation.kpi_monitor import KpiMonitor, KpiThreshold
from enterprise_intelligence.observation.anomaly_detection import AnomalyDetection
from enterprise_intelligence.observation.sources.adapters import (
    BaseSourceAdapter,
    RankingSource,
    CrawlSource,
    TechnicalSource,
    BacklinkSource,
    CompetitorSource,
    AnalyticsSource,
    ReputationSource,
    LocalSeoSource,
    ContentSource,
    CostSource,
    HealthSource,
    SecuritySource,
)


# ---- Fixtures ----

def _make_event(
    *,
    category: EventCategory = EventCategory.RANKING,
    severity: EventSeverity = EventSeverity.INFO,
    data: dict | None = None,
    confidence: float = 1.0,
    tenant_id: str = "t1",
    site_id: str = "s1",
    created_at: datetime | None = None,
) -> ObservationEvent:
    return ObservationEvent(
        tenant_id=tenant_id,
        site_id=site_id,
        category=category,
        severity=severity,
        source_engine="test",
        source_ref="ref-1",
        title="Test event",
        description="Test event description",
        data=data or {},
        confidence=confidence,
        created_at=created_at or datetime.now(timezone.utc),
    )


# ---- Models ----

class TestObservationModels:
    def test_event_creation(self):
        event = _make_event()
        assert event.tenant_id == "t1"
        assert event.category == EventCategory.RANKING
        assert event.severity == EventSeverity.INFO
        assert event.version == 1

    def test_event_has_auto_id(self):
        e1 = _make_event()
        e2 = _make_event()
        assert e1.id != e2.id

    def test_correlated_group(self):
        group = CorrelatedEventGroup(
            tenant_id="t1",
            event_ids=["e1", "e2"],
            correlation_type="ranking+technical",
            confidence=0.8,
        )
        assert len(group.event_ids) == 2
        assert group.correlation_type == "ranking+technical"


# ---- EventBus ----

class TestEventBus:
    def test_publish_delivers_to_subscriber(self):
        bus = EventBus()
        received = []

        class Sub:
            def on_event(self, event):
                received.append(event)

        bus.subscribe("ranking", Sub())
        bus.publish(_make_event(category=EventCategory.RANKING))
        assert len(received) == 1

    def test_wildcard_subscriber_receives_all(self):
        bus = EventBus()
        received = []

        class Sub:
            def on_event(self, event):
                received.append(event)

        bus.subscribe("*", Sub())
        bus.publish(_make_event(category=EventCategory.RANKING))
        bus.publish(_make_event(category=EventCategory.TECHNICAL))
        assert len(received) == 2

    def test_subscriber_error_does_not_block_others(self):
        bus = EventBus()
        received = []

        class BadSub:
            def on_event(self, event):
                raise RuntimeError("boom")

        class GoodSub:
            def on_event(self, event):
                received.append(event)

        bus.subscribe("*", BadSub())
        bus.subscribe("*", GoodSub())
        bus.publish(_make_event())
        assert len(received) == 1

    def test_published_count(self):
        bus = EventBus()
        bus.publish(_make_event())
        bus.publish(_make_event())
        assert bus.published_count == 2

    def test_subscriber_count(self):
        bus = EventBus()

        class Sub:
            def on_event(self, event):
                pass

        bus.subscribe("ranking", Sub())
        bus.subscribe("*", Sub())
        assert bus.subscriber_count == 2


# ---- Classifier ----

class TestEventClassifier:
    def test_ranking_critical(self):
        cls = EventClassifier()
        event = _make_event(
            category=EventCategory.RANKING,
            data={"position_change": -15},
        )
        result = cls.classify(event)
        assert result.severity == EventSeverity.CRITICAL

    def test_ranking_warning(self):
        cls = EventClassifier()
        event = _make_event(
            category=EventCategory.RANKING,
            data={"position_change": -5},
        )
        result = cls.classify(event)
        assert result.severity == EventSeverity.WARNING

    def test_ranking_info(self):
        cls = EventClassifier()
        event = _make_event(
            category=EventCategory.RANKING,
            data={"position_change": -1},
        )
        result = cls.classify(event)
        assert result.severity == EventSeverity.INFO

    def test_technical_critical(self):
        cls = EventClassifier()
        event = _make_event(
            category=EventCategory.TECHNICAL,
            data={"health_score": 0.1},
        )
        result = cls.classify(event)
        assert result.severity == EventSeverity.CRITICAL

    def test_backlink_warning(self):
        cls = EventClassifier()
        event = _make_event(
            category=EventCategory.BACKLINK,
            data={"loss_percentage": 0.08},
        )
        result = cls.classify(event)
        assert result.severity == EventSeverity.WARNING

    def test_unknown_category_info(self):
        cls = EventClassifier()
        event = _make_event(category=EventCategory.LOCAL_SEO)
        result = cls.classify(event)
        assert result.severity == EventSeverity.INFO


# ---- Prioritizer ----

class TestEventPrioritizer:
    def test_critical_events_ranked_higher(self):
        pri = EventPrioritizer()
        low = _make_event(severity=EventSeverity.INFO, category=EventCategory.CONTENT)
        high = _make_event(severity=EventSeverity.CRITICAL, category=EventCategory.RANKING)
        result = pri.prioritize([low, high])
        assert result[0].severity == EventSeverity.CRITICAL

    def test_score_normalised_0_to_1(self):
        pri = EventPrioritizer()
        event = _make_event(severity=EventSeverity.CRITICAL, confidence=1.0)
        score = pri.score(event)
        assert 0.0 <= score <= 1.0

    def test_higher_confidence_scores_higher(self):
        pri = EventPrioritizer()
        low_conf = _make_event(severity=EventSeverity.WARNING, confidence=0.2)
        high_conf = _make_event(severity=EventSeverity.WARNING, confidence=0.9)
        assert pri.score(high_conf) > pri.score(low_conf)


# ---- Correlation ----

class TestEventCorrelationEngine:
    def test_correlates_cross_source_events(self):
        engine = EventCorrelationEngine(window_minutes=60)
        now = datetime.now(timezone.utc)
        e1 = _make_event(
            category=EventCategory.RANKING,
            data={"page_id": "page-1"},
            created_at=now,
        )
        e2 = _make_event(
            category=EventCategory.TECHNICAL,
            data={"page_id": "page-1"},
            created_at=now + timedelta(minutes=5),
        )
        groups = engine.correlate([e1, e2])
        assert len(groups) == 1
        assert len(groups[0].event_ids) == 2

    def test_no_correlation_same_category(self):
        engine = EventCorrelationEngine(window_minutes=60)
        now = datetime.now(timezone.utc)
        e1 = _make_event(category=EventCategory.RANKING, data={"page_id": "p1"}, created_at=now)
        e2 = _make_event(category=EventCategory.RANKING, data={"page_id": "p1"}, created_at=now)
        groups = engine.correlate([e1, e2])
        assert len(groups) == 0

    def test_no_correlation_outside_window(self):
        engine = EventCorrelationEngine(window_minutes=10)
        now = datetime.now(timezone.utc)
        e1 = _make_event(category=EventCategory.RANKING, data={"page_id": "p1"}, created_at=now)
        e2 = _make_event(category=EventCategory.TECHNICAL, data={"page_id": "p1"}, created_at=now + timedelta(minutes=30))
        groups = engine.correlate([e1, e2])
        assert len(groups) == 0

    def test_no_correlation_no_shared_keys(self):
        engine = EventCorrelationEngine(window_minutes=60)
        now = datetime.now(timezone.utc)
        e1 = _make_event(category=EventCategory.RANKING, data={"page_id": "p1"}, created_at=now)
        e2 = _make_event(category=EventCategory.TECHNICAL, data={"page_id": "p2"}, created_at=now)
        groups = engine.correlate([e1, e2])
        assert len(groups) == 0

    def test_single_event_no_correlation(self):
        engine = EventCorrelationEngine()
        groups = engine.correlate([_make_event()])
        assert len(groups) == 0


# ---- Drift Detection ----

class TestDriftDetection:
    def test_significant_drift(self):
        dd = DriftDetection(threshold_pct=0.10)
        result = dd.detect("traffic", [100, 100, 100], [120, 125, 130])
        assert result.is_significant
        assert result.drift_magnitude > 0

    def test_no_drift(self):
        dd = DriftDetection(threshold_pct=0.10)
        result = dd.detect("traffic", [100, 100, 100], [100, 101, 99])
        assert not result.is_significant

    def test_empty_values(self):
        dd = DriftDetection()
        result = dd.detect("traffic", [], [])
        assert not result.is_significant
        assert result.window_size == 0

    def test_negative_drift(self):
        dd = DriftDetection(threshold_pct=0.10)
        result = dd.detect("traffic", [100, 100, 100], [80, 75, 70])
        assert result.is_significant
        assert result.drift_magnitude < 0


# ---- Trend Detection ----

class TestTrendDetection:
    def test_upward_trend(self):
        td = TrendDetection(min_r_squared=0.5, min_slope=0.01)
        result = td.detect("traffic", [10, 20, 30, 40, 50])
        assert result.direction == "up"
        assert result.is_significant
        assert result.slope > 0

    def test_downward_trend(self):
        td = TrendDetection(min_r_squared=0.5, min_slope=0.01)
        result = td.detect("traffic", [50, 40, 30, 20, 10])
        assert result.direction == "down"
        assert result.is_significant
        assert result.slope < 0

    def test_stable_no_trend(self):
        td = TrendDetection(min_r_squared=0.5, min_slope=1.0)
        result = td.detect("traffic", [100, 100, 100, 100, 100])
        assert result.direction == "stable"
        assert not result.is_significant

    def test_too_few_values(self):
        td = TrendDetection()
        result = td.detect("traffic", [10, 20])
        assert result.direction == "stable"
        assert not result.is_significant


# ---- KPI Monitor ----

class TestKpiMonitor:
    def test_critical_alert_below(self):
        monitor = KpiMonitor([
            KpiThreshold("traffic", warning_threshold=1000, critical_threshold=500, direction="below"),
        ])
        alert = monitor.check("traffic", 400)
        assert alert is not None
        assert alert.severity == EventSeverity.CRITICAL

    def test_warning_alert_below(self):
        monitor = KpiMonitor([
            KpiThreshold("traffic", warning_threshold=1000, critical_threshold=500, direction="below"),
        ])
        alert = monitor.check("traffic", 800)
        assert alert is not None
        assert alert.severity == EventSeverity.WARNING

    def test_no_alert(self):
        monitor = KpiMonitor([
            KpiThreshold("traffic", warning_threshold=1000, critical_threshold=500, direction="below"),
        ])
        alert = monitor.check("traffic", 1500)
        assert alert is None

    def test_above_direction(self):
        monitor = KpiMonitor([
            KpiThreshold("cost", warning_threshold=100, critical_threshold=200, direction="above"),
        ])
        alert = monitor.check("cost", 250)
        assert alert is not None
        assert alert.severity == EventSeverity.CRITICAL

    def test_unknown_kpi_no_alert(self):
        monitor = KpiMonitor()
        alert = monitor.check("unknown", 42)
        assert alert is None

    def test_check_all(self):
        monitor = KpiMonitor([
            KpiThreshold("traffic", warning_threshold=1000, critical_threshold=500, direction="below"),
            KpiThreshold("cost", warning_threshold=100, critical_threshold=200, direction="above"),
        ])
        alerts = monitor.check_all({"traffic": 400, "cost": 250})
        assert len(alerts) == 2


# ---- Anomaly Detection ----

class TestAnomalyDetection:
    def test_zscore_anomaly(self):
        ad = AnomalyDetection(z_threshold=2.0)
        result = ad.detect_zscore("metric", 100, [10, 12, 11, 10, 13, 11, 12])
        assert result.is_anomaly
        assert result.method == "z_score"

    def test_zscore_normal(self):
        ad = AnomalyDetection(z_threshold=2.0)
        result = ad.detect_zscore("metric", 12, [10, 12, 11, 10, 13, 11, 12])
        assert not result.is_anomaly

    def test_iqr_anomaly(self):
        ad = AnomalyDetection(iqr_factor=1.5)
        result = ad.detect_iqr("metric", 100, [10, 12, 11, 10, 13, 11, 12, 10])
        assert result.is_anomaly
        assert result.method == "iqr"

    def test_iqr_normal(self):
        ad = AnomalyDetection(iqr_factor=1.5)
        result = ad.detect_iqr("metric", 12, [10, 12, 11, 10, 13, 11, 12, 10])
        assert not result.is_anomaly

    def test_too_few_values_zscore(self):
        ad = AnomalyDetection()
        result = ad.detect_zscore("metric", 50, [10])
        assert not result.is_anomaly

    def test_too_few_values_iqr(self):
        ad = AnomalyDetection()
        result = ad.detect_iqr("metric", 50, [10, 20])
        assert not result.is_anomaly


# ---- Source Adapters ----

class TestSourceAdapters:
    def test_all_12_adapters_exist(self):
        """Verify all 12 source adapters are importable and concrete."""
        adapters = [
            RankingSource, CrawlSource, TechnicalSource, BacklinkSource,
            CompetitorSource, AnalyticsSource, ReputationSource, LocalSeoSource,
            ContentSource, CostSource, HealthSource, SecuritySource,
        ]
        assert len(adapters) == 12
        for cls in adapters:
            assert issubclass(cls, BaseSourceAdapter)

    def test_adapters_return_empty_without_repo(self):
        """Adapters with no connected repo return empty lists (not errors)."""
        for cls in [RankingSource, CrawlSource, TechnicalSource, BacklinkSource,
                    CompetitorSource, AnalyticsSource, ReputationSource, LocalSeoSource,
                    ContentSource, CostSource, HealthSource, SecuritySource]:
            adapter = cls()
            result = adapter.poll("t1", "s1")
            assert isinstance(result, list)


# ---- Structural Governance Bypass Test ----

class TestObservationGovernanceBypass:
    """Structural test: the observation package must contain ZERO imports of
    any governance-gated component (GovernanceGate, AgentRuntime, Executor,
    GovernanceService).

    This is the most important safety test for Phase 1: observation produces
    data only, it must never trigger any governed action.
    """

    _FORBIDDEN_IMPORTS = {
        "GovernanceGate",
        "AgentRuntime",
        "Executor",
        "GovernanceService",
    }

    def test_no_governance_imports_in_observation(self):
        """Scan all .py files in the observation package for forbidden imports."""
        observation_dir = os.path.join(
            os.path.dirname(__file__),
            os.pardir, os.pardir,
            "enterprise_intelligence", "observation",
        )
        observation_dir = os.path.normpath(observation_dir)

        violations: list[str] = []

        for root, _dirs, files in os.walk(observation_dir):
            for fname in files:
                if not fname.endswith(".py"):
                    continue
                filepath = os.path.join(root, fname)
                with open(filepath, "r", encoding="utf-8") as f:
                    source = f.read()

                for forbidden in self._FORBIDDEN_IMPORTS:
                    if forbidden in source:
                        violations.append(
                            f"{os.path.relpath(filepath, observation_dir)}: "
                            f"contains reference to '{forbidden}'"
                        )

        assert not violations, (
            "Observation package must not reference governance-gated components:\n"
            + "\n".join(violations)
        )
