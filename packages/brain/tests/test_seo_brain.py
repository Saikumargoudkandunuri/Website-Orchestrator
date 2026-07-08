"""Tests for SeoBrain aggregation service.

Verifies that ``SeoBrain`` correctly assembles a ``SiteSynthesis`` from
fixture engine outputs (mocked repositories) covering all ten M3 and ten
M4 engines.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock

import pytest

from brain.models import SiteSynthesis
from brain.services import SeoBrain


# --- Fixtures: mock engine outputs ---

def _make_mock_report(
    *,
    version: int = 1,
    data: dict[str, Any] | None = None,
    has_model_dump: bool = True,
    data_completeness: float = 1.0,
) -> Any:
    """Create a mock engine report that mimics a Pydantic model."""
    report = MagicMock()
    report.version = version
    report.computed_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
    report.data_completeness = data_completeness
    dump_data = data or {"version": version}
    report.model_dump.return_value = dump_data
    return report


def _make_mock_repo(
    report: Any | None = None,
) -> Any:
    """Create a mock repository with ``get_latest`` returning ``report``."""
    repo = MagicMock()
    repo.get_latest.return_value = report
    return repo


class TestSeoBrainAggregation:
    """SeoBrain produces correct SiteSynthesis from fixture engine outputs."""

    def test_empty_repos_produces_synthesis_with_no_data(self) -> None:
        brain = SeoBrain(m3_repos={}, m4_repos={})
        synthesis = brain.get_synthesis("tenant-1", "site-1")

        assert isinstance(synthesis, SiteSynthesis)
        assert synthesis.site_id == "site-1"
        assert synthesis.tenant_id == "tenant-1"
        assert synthesis.engines_with_data == 0
        assert len(synthesis.m3_engines) == 10
        assert len(synthesis.m4_engines) == 10
        for summary in synthesis.m3_engines.values():
            assert not summary.has_data
        for summary in synthesis.m4_engines.values():
            assert not summary.has_data

    def test_all_m3_engines_with_data(self) -> None:
        m3_repos = {}
        for _, repo_key in SeoBrain.M3_ENGINES:
            report = _make_mock_report(version=3)
            m3_repos[repo_key] = _make_mock_repo(report)

        brain = SeoBrain(m3_repos=m3_repos, m4_repos={})
        synthesis = brain.get_synthesis("tenant-1", "site-1")

        assert synthesis.engines_with_data == 10
        for name, summary in synthesis.m3_engines.items():
            assert summary.has_data, f"M3 engine {name} should have data"
            assert summary.engine_category == "m3"
            assert summary.latest_version == 3

    def test_all_m4_engines_with_data(self) -> None:
        m4_repos = {}
        for _, repo_key in SeoBrain.M4_ENGINES:
            report = _make_mock_report(version=2)
            m4_repos[repo_key] = _make_mock_repo(report)

        brain = SeoBrain(m3_repos={}, m4_repos=m4_repos)
        synthesis = brain.get_synthesis("tenant-1", "site-1")

        assert synthesis.engines_with_data == 10
        for name, summary in synthesis.m4_engines.items():
            assert summary.has_data, f"M4 engine {name} should have data"
            assert summary.engine_category == "m4"
            assert summary.latest_version == 2

    def test_all_twenty_engines_with_data(self) -> None:
        m3_repos = {}
        for _, repo_key in SeoBrain.M3_ENGINES:
            m3_repos[repo_key] = _make_mock_repo(_make_mock_report())
        m4_repos = {}
        for _, repo_key in SeoBrain.M4_ENGINES:
            m4_repos[repo_key] = _make_mock_repo(_make_mock_report())

        brain = SeoBrain(m3_repos=m3_repos, m4_repos=m4_repos)
        synthesis = brain.get_synthesis("tenant-1", "site-1")

        assert synthesis.engines_with_data == 20
        assert synthesis.total_engines == 20

    def test_opportunity_metrics_extracted(self) -> None:
        opp_report = _make_mock_report(data={
            "version": 1,
            "opportunities": [{"id": "opp-1"}, {"id": "opp-2"}, {"id": "opp-3"}],
        })
        m3_repos = {"opportunity_repo": _make_mock_repo(opp_report)}

        brain = SeoBrain(m3_repos=m3_repos, m4_repos={})
        synthesis = brain.get_synthesis("tenant-1", "site-1")

        assert synthesis.total_opportunities == 3

    def test_recommendation_metrics_extracted(self) -> None:
        rec_report = _make_mock_report(data={
            "version": 1,
            "recommendations": [{"id": "r-1"}, {"id": "r-2"}],
        })
        m3_repos = {"recommendation_repo": _make_mock_repo(rec_report)}

        brain = SeoBrain(m3_repos=m3_repos, m4_repos={})
        synthesis = brain.get_synthesis("tenant-1", "site-1")

        assert synthesis.total_recommendations == 2

    def test_seo_score_extracted(self) -> None:
        score_report = _make_mock_report(data={
            "version": 1,
            "overall_score": 78.5,
        })
        m3_repos = {"seo_score_repo": _make_mock_repo(score_report)}

        brain = SeoBrain(m3_repos=m3_repos, m4_repos={})
        synthesis = brain.get_synthesis("tenant-1", "site-1")

        assert synthesis.overall_seo_score == 78.5

    def test_repo_returning_none_marks_engine_without_data(self) -> None:
        m3_repos = {"technical_seo_repo": _make_mock_repo(None)}
        brain = SeoBrain(m3_repos=m3_repos, m4_repos={})
        synthesis = brain.get_synthesis("tenant-1", "site-1")

        assert not synthesis.m3_engines["technical_seo"].has_data

    def test_repo_throwing_exception_marks_engine_without_data(self) -> None:
        broken_repo = MagicMock()
        broken_repo.get_latest.side_effect = Exception("DB down")
        m3_repos = {"technical_seo_repo": broken_repo}

        brain = SeoBrain(m3_repos=m3_repos, m4_repos={})
        synthesis = brain.get_synthesis("tenant-1", "site-1")

        assert not synthesis.m3_engines["technical_seo"].has_data

    def test_partial_m3_m4_data(self) -> None:
        m3_repos = {
            "technical_seo_repo": _make_mock_repo(_make_mock_report()),
            "keyword_repo": _make_mock_repo(_make_mock_report()),
        }
        m4_repos = {
            "local_seo_repo": _make_mock_repo(_make_mock_report()),
        }

        brain = SeoBrain(m3_repos=m3_repos, m4_repos=m4_repos)
        synthesis = brain.get_synthesis("tenant-1", "site-1")

        assert synthesis.engines_with_data == 3
        assert synthesis.m3_engines["technical_seo"].has_data
        assert synthesis.m3_engines["keyword_intelligence"].has_data
        assert not synthesis.m3_engines["content_intelligence"].has_data
        assert synthesis.m4_engines["local_seo"].has_data
        assert not synthesis.m4_engines["reputation_management"].has_data

    def test_data_completeness_propagated(self) -> None:
        report = _make_mock_report(data_completeness=0.75)
        m3_repos = {"technical_seo_repo": _make_mock_repo(report)}

        brain = SeoBrain(m3_repos=m3_repos, m4_repos={})
        synthesis = brain.get_synthesis("tenant-1", "site-1")

        assert synthesis.m3_engines["technical_seo"].data_completeness == 0.75
