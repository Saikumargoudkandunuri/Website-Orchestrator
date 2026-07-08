"""Tests for the Decision Engine and its repositories."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from brain.decision.engine import DecisionEngine, HistoricalOutcomeTracker
from brain.decision.models import PrioritizedDecision
from brain.models import SiteSynthesis, EngineSummary
from brain.knowledge_graph.models import WebsiteKnowledgeGraph


class TestDecisionEngine:
    """Decision Engine evaluation and scoring tests."""

    def test_evaluate_synthesis_generates_decisions(self) -> None:
        dec_repo = MagicMock()
        hist_repo = MagicMock()
        engine = DecisionEngine(decision_repo=dec_repo, historical_repo=hist_repo)

        synthesis = SiteSynthesis(
            id="synth-1",
            tenant_id="tenant-1",
            site_id="site-1",
            engines_with_data=1,
            m3_engines={
                "opportunity_discovery": EngineSummary(
                    engine_name="opportunity_discovery",
                    engine_category="m3",
                    latest_version=1,
                    has_data=True,
                )
            }
        )
        graph = WebsiteKnowledgeGraph(site_id="site-1", tenant_id="tenant-1")

        decisions = engine.evaluate_synthesis(synthesis, graph)
        assert len(decisions) == 1
        d = decisions[0]
        assert d.source_engine == "opportunity_discovery"
        assert d.composite_score > 0
        assert len(d.dimensions) == 7
        dec_repo.save.assert_called_once_with(d)


class TestHistoricalOutcomeTracker:
    """Outcome tracker baseline and outcome tests."""

    def test_record_baseline(self) -> None:
        hist_repo = MagicMock()
        tracker = HistoricalOutcomeTracker(historical_repo=hist_repo)

        decision = PrioritizedDecision(
            id="dec-1",
            tenant_id="t1",
            site_id="s1",
            title="Test",
            description="Desc",
            source_engine="e1",
            source_ref="r1",
            recommended_action="Do things",
        )

        outcome = tracker.record_baseline(decision, {"traffic": 100})
        assert outcome.decision_id == "dec-1"
        assert outcome.baseline_metrics["traffic"] == 100
        hist_repo.save.assert_called_once_with(outcome)

    def test_record_outcome_success(self) -> None:
        hist_repo = MagicMock()
        tracker = HistoricalOutcomeTracker(historical_repo=hist_repo)

        # Baseline: traffic = 100
        mock_outcome = MagicMock()
        mock_outcome.baseline_metrics = {"traffic": 100.0}
        hist_repo.get_by_decision.return_value = mock_outcome

        tracker.record_outcome("t1", "dec-1", {"traffic": 110.0})  # +10%
        
        assert mock_outcome.outcome_metrics["traffic"] == 110.0
        assert mock_outcome.is_success is True
        assert mock_outcome.performance_delta == 0.1
        hist_repo.save.assert_called_with(mock_outcome)

    def test_record_outcome_failure(self) -> None:
        hist_repo = MagicMock()
        tracker = HistoricalOutcomeTracker(historical_repo=hist_repo)

        # Baseline: traffic = 100
        mock_outcome = MagicMock()
        mock_outcome.baseline_metrics = {"traffic": 100.0}
        hist_repo.get_by_decision.return_value = mock_outcome

        tracker.record_outcome("t1", "dec-1", {"traffic": 102.0})  # +2% (not enough for success)
        
        assert mock_outcome.is_success is False
        assert mock_outcome.performance_delta == 0.02
        hist_repo.save.assert_called_with(mock_outcome)
