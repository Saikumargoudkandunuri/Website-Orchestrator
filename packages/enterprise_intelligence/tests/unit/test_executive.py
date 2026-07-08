"""Phase 9 — Executive Intelligence unit and grounding tests.

Tests cover: BriefingEngine reporting, grounding constraints, hallucination pressure,
and zero metric calculation verification.
"""

from __future__ import annotations

import os
import pytest

from core.results import Ok
from intelligence.ai.provider_interface import AICompletionResponse
from enterprise_intelligence.executive.engine import BriefingEngine, ReportGenerator, ExecutiveReport


class MockAIProvider:
    def complete(self, request):
        return Ok(AICompletionResponse(
            raw_text="The daily traffic reached 5000 visits, average position is #12.",
            model="gpt-4",
        ))

    def name(self):
        return "mock_ai"

    def supports_json_mode(self):
        return False


class TestExecutiveBriefing:
    def test_briefing_generation_grounded(self):
        provider = MockAIProvider()
        engine = BriefingEngine(provider)
        
        facts = [
            {"metric": "traffic", "value": 5000, "source_ref": "analytics-1"},
            {"metric": "average position", "value": 12, "source_ref": "rank-5"},
        ]
        
        report = engine.generate_briefing("t1", "s1", "daily_summary", facts)
        assert report.report_type == "daily_summary"
        assert "traffic" in facts[0]["metric"]
        assert "analytics-1" in report.grounded_evidence
        assert "rank-5" in report.grounded_evidence
        assert "5000" in report.summary_text

    def test_hallucination_pressure_missing_facts(self):
        """Verify that when no facts are retrieved, the engine hedges or omits information."""
        provider = MockAIProvider()
        engine = BriefingEngine(provider)
        
        # Scenario: Empty facts list
        report = engine.generate_briefing("t1", "s1", "daily_summary", retrieved_facts=[])
        assert "Insufficient data" in report.summary_text
        assert len(report.grounded_evidence) == 0


class TestExecutiveZeroCalculation:
    """Verify that ReportGenerator has no custom arithmetic logic or metric formulas.

    It must only extract facts from repositories and delegate formatting.
    """

    def test_no_arithmetic_in_reporting_code(self):
        generator_file = os.path.join(
            os.path.dirname(__file__),
            os.pardir, os.pardir,
            "enterprise_intelligence", "executive", "engine.py"
        )
        generator_file = os.path.normpath(generator_file)
        
        with open(generator_file, "r", encoding="utf-8") as f:
            source = f.read()

        # Check for arithmetic calculations
        forbidden_patterns = ["math.sqrt", "variance =", "std_dev =", "mean =", " / len"]
        violations = [pat for pat in forbidden_patterns if pat in source]
        assert not violations, f"ReportGenerator safety violation: contains metric calculation patterns {violations}"
