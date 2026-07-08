"""Analytics Intelligence services (§4.8)."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from core.results import Err, Ok, Result
from growth.analytics_intelligence.models import AnalyticsReport, AnalyticsSnapshot
from growth.shared.provider_abstraction.analytics_data_provider_interface import AnalyticsDataProvider
from growth.errors import GrowthAnalysisError

__all__ = ["AnalyticsService"]


class AnalyticsService:
    """Analytics Intelligence business logic using provider-abstracted data."""

    def __init__(self, provider: AnalyticsDataProvider):
        self._provider = provider

    def analyze(self, site_id: str) -> Result[AnalyticsReport, GrowthAnalysisError]:
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=30)
        snapshot_result = self._provider.fetch_snapshot(site_id, start, end)
        pages_result = self._provider.fetch_top_pages(site_id, limit=10)
        keywords_result = self._provider.fetch_top_keywords(site_id, limit=20)
        if snapshot_result.is_err:
            return Err(GrowthAnalysisError(f"Failed to fetch analytics snapshot: {snapshot_result.unwrap_err()}"))
        if pages_result.is_err:
            return Err(GrowthAnalysisError(f"Failed to fetch top pages: {pages_result.unwrap_err()}"))
        if keywords_result.is_err:
            return Err(GrowthAnalysisError(f"Failed to fetch top keywords: {keywords_result.unwrap_err()}"))

        raw = snapshot_result.unwrap()
        snapshot = AnalyticsSnapshot(
            snapshot_id=f"analytics-{site_id}-{int(raw.captured_at.timestamp())}",
            site_id=site_id,
            captured_at=raw.captured_at,
            sessions=raw.sessions,
            users=raw.users,
            pageviews=raw.pageviews,
            bounce_rate=raw.bounce_rate or 0.0,
            avg_session_duration=raw.avg_session_duration_s or 0.0,
            conversions=raw.conversions,
            data_source=raw.data_source,
        )
        top_pages = [page.model_dump(mode="json") for page in pages_result.unwrap()]
        top_keywords = [keyword.model_dump(mode="json") for keyword in keywords_result.unwrap()]
        growth_trend = {
            "metric_name": "sessions",
            "aggregation": "sum",
            "series": [{"date": snapshot.captured_at.date().isoformat(), "value": snapshot.sessions}],
        }
        report = AnalyticsReport(
            site_id=site_id,
            snapshot_count=1,
            latest_snapshot_at=snapshot.captured_at,
            top_pages=top_pages,
            top_keywords=top_keywords,
            growth_trend=growth_trend,
            ai_summary=(
                f"{site_id} recorded {snapshot.sessions} sessions, {snapshot.users} users, "
                f"and {snapshot.conversions or 0} conversions in the latest analytics window."
            ),
            computed_at=datetime.now(timezone.utc),
            data_source=snapshot.data_source,
            data_completeness=raw.data_completeness,
        )
        return Ok(report)