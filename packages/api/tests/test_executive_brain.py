"""Milestone 5 — Editorial Calendar: annual roadmap horizon + autofill.

``plan_roadmap`` buckets Missions by priority/capacity into daily -> weekly ->
monthly -> quarterly -> annual. These tests exercise the bucket-assignment and
autofill logic directly against real ``Mission`` objects (no mocked engine
output) so the behaviour is deterministic and independent of any specific
specialist's evidence.
"""
from __future__ import annotations

from api import executive_brain as brain


def _mission(
    *, category: str, difficulty: str, effort_hours: float, priority_score: float,
    business_priority: str = "medium", title: str = "Mission",
) -> brain.Mission:
    return brain.Mission(
        id=f"msn_{title}_{category}_{effort_hours}",
        title=title,
        description="",
        category=category,
        assigned_agent="Test Agent",
        assigned_department="content",
        source_agent="test",
        signal_provenance="observed_live_crawl",
        forecast_basis="test",
        seo_impact=50,
        expected_ranking_improvement="",
        traffic_gain="",
        expected_traffic_gain="",
        expected_leads="",
        expected_revenue_impact="",
        business_value=50,
        business_priority=business_priority,
        difficulty=difficulty,
        effort_hours=effort_hours,
        confidence=0.8,
        required_budget="",
        required_ai_provider="",
        required_tools=[],
        required_specialist_agents=[],
        estimated_completion_time="",
        rollback_strategy="",
        dependencies=[],
        priority_score=priority_score,
        reasoning="",
        evidence=[],
        learning={"multiplier": 1.0, "confidence_delta": 0.0, "samples": 0, "success_rate": None},
    )


def test_plan_roadmap_has_annual_horizon_with_capacity() -> None:
    result = brain.plan_roadmap([])
    assert result["next_365_days"] == []
    assert result["annual"] == []
    assert "annual_hours" in result["capacity"]
    assert result["capacity"]["annual_hours"] > result["capacity"]["quarterly_hours"]
    assert "next_365_days" in result["capacity"]["scheduled_hours"]


def test_plan_roadmap_overflows_beyond_quarterly_into_annual() -> None:
    # High-difficulty, non-editorial missions skip the daily/weekly gates
    # entirely and fill monthly (120h) then quarterly (400h) before overflow.
    missions = [
        _mission(
            category="technical_seo", difficulty="high", effort_hours=24.0,
            priority_score=100.0 - i, business_priority="medium", title=f"tech-{i}",
        )
        for i in range(25)
    ]
    result = brain.plan_roadmap(missions)

    # 120h / 24h = 5 fit monthly; 400h / 24h = 16 fit quarterly; remaining 4 overflow to annual.
    assert len(result["next_30_days"]) == 5
    assert len(result["next_90_days"]) == 16
    assert len(result["next_365_days"]) == 4
    assert len(result["annual"]) == 4
    # No content/strategy mission exists anywhere, so the Editorial Calendar
    # autofill correctly finds nothing to promote and leaves daily/weekly empty.
    assert result["today"] == []
    assert result["next_7_days"] == []


def test_editorial_calendar_autofill_promotes_content_into_empty_weekly_horizon() -> None:
    # M0: small, critical content mission -> lands in "today" on its own,
    # so the daily horizon already satisfies the Editorial Calendar and the
    # autofill pass must leave it alone.
    daily_content = _mission(
        category="content", difficulty="low", effort_hours=1.0, priority_score=95.0,
        business_priority="critical", title="daily-content",
    )
    # M1: a purely technical mission that naturally fills the weekly horizon
    # but carries no content/strategy value for the Editorial Calendar.
    weekly_technical = _mission(
        category="technical_seo", difficulty="medium", effort_hours=10.0,
        priority_score=90.0, business_priority="medium", title="weekly-technical",
    )
    # M2: a real, evidenced content mission that would otherwise only reach
    # the monthly horizon under strict priority/capacity bin-packing.
    monthly_content = _mission(
        category="content", difficulty="high", effort_hours=5.0, priority_score=70.0,
        business_priority="medium", title="monthly-content",
    )

    result = brain.plan_roadmap([daily_content, weekly_technical, monthly_content])

    # Daily already had real content -> untouched by autofill.
    assert len(result["today"]) == 1
    assert result["today"][0]["autofilled"] is False

    # Weekly had no content/strategy mission on its own -> the Editorial
    # Calendar promoted the monthly content mission into it automatically.
    weekly_titles = {m["title"] for m in result["next_7_days"]}
    assert "weekly-technical" in weekly_titles
    assert "monthly-content" in weekly_titles
    promoted = next(m for m in result["next_7_days"] if m["title"] == "monthly-content")
    assert promoted["autofilled"] is True
    assert promoted["horizon"] == "weekly"
    assert "Editorial Calendar autofill" in promoted["reasoning"]

    # The promoted mission no longer double-counts in its original horizon.
    assert all(m["title"] != "monthly-content" for m in result["next_30_days"])
