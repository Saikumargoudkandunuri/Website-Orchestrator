"""Rank Tracking services."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from core.results import Err, Ok, Result
from growth.errors import GrowthAnalysisError
from growth.rank_tracking.models import (
    RankTrackingReport,
    RankingChange,
    RankingSnapshot,
    TimeSeriesExport,
    TrackedKeyword,
)
from growth.shared.jobs.job_queue_interface import JobDefinition, JobQueue
from growth.shared.provider_abstraction.rank_tracking_provider_interface import RankTrackingProvider

if TYPE_CHECKING:
    from growth.rank_tracking.repositories import RankTrackingRepository

__all__ = ["RankTrackingService"]


class RankTrackingService:
    """Capture ranking snapshots and assemble rank-tracking reports."""

    def __init__(
        self,
        provider: RankTrackingProvider,
        repository: "RankTrackingRepository",
        job_queue: JobQueue,
    ) -> None:
        self._provider = provider
        self._repo = repository
        self._job_queue = job_queue

    def add_keyword(
        self,
        keyword: TrackedKeyword,
        *,
        site_id: str,
        organization_id: str | None = None,
        client_id: str | None = None,
    ) -> Result[TrackedKeyword, GrowthAnalysisError]:
        saved = self._repo.save_tracked_keyword(
            keyword,
            org_id=organization_id,
            client_id=client_id,
            site_id=site_id,
        )
        if saved.is_err:
            return Err(GrowthAnalysisError(str(saved.unwrap_err())))
        return Ok(saved.unwrap())

    def capture_rankings_now(
        self,
        site_id: str,
        device: str = "desktop",
        geo: str = "US",
    ) -> Result[list[RankingSnapshot], GrowthAnalysisError]:
        """Capture rankings for all active tracked keywords for a site."""
        tracked_result = self._repo.get_tracked_keywords(site_id, active_only=True)
        if tracked_result.is_err:
            return Err(GrowthAnalysisError(f"Failed to get tracked keywords: {tracked_result.unwrap_err()}"))

        tracked_keywords = [
            kw for kw in tracked_result.unwrap()
            if kw.device == device and (kw.geo or "") == (geo or "")
        ]
        if not tracked_keywords:
            return Ok([])

        provider_result = self._provider.fetch_rankings(
            site_id=site_id,
            keywords=[kw.keyword for kw in tracked_keywords],
            device=device,
            geo=geo,
        )
        if provider_result.is_err:
            return Err(GrowthAnalysisError(f"Failed to fetch rankings: {provider_result.unwrap_err()}"))

        by_keyword = {kw.keyword: kw for kw in tracked_keywords}
        snapshots: list[RankingSnapshot] = []
        for provider_snapshot in provider_result.unwrap():
            tracked = by_keyword.get(provider_snapshot.keyword)
            if tracked is None:
                continue
            captured_at = provider_snapshot.captured_at or datetime.now(timezone.utc)
            snapshots.append(RankingSnapshot(
                snapshot_id=uuid.uuid4().hex,
                keyword_id=tracked.keyword_id,
                keyword=tracked.keyword,
                page_id=tracked.page_id,
                position=int(provider_snapshot.position) if provider_snapshot.position is not None else None,
                device=device,
                geo=geo,
                captured_at=captured_at,
                url=provider_snapshot.url,
                data_source=provider_snapshot.data_source,
            ))

        save_result = self._repo.save_snapshots(snapshots, site_id)
        if save_result.is_err:
            return Err(GrowthAnalysisError(f"Failed to save snapshots: {save_result.unwrap_err()}"))
        return Ok(snapshots)

    def schedule_rank_capture(
        self,
        site_id: str,
        cadence: str,
    ) -> Result[str, GrowthAnalysisError]:
        """Schedule recurring rank capture through the injected job queue."""
        from growth.shared.jobs.scheduled_job_registry import default_scheduled_jobs

        job_type_map = {
            "daily": "rank_tracking_capture_daily",
            "weekly": "rank_tracking_capture_weekly",
            "monthly": "rank_tracking_capture_monthly",
        }
        job_type = job_type_map.get(cadence)
        if job_type is None:
            return Err(GrowthAnalysisError(f"Invalid cadence: {cadence}"))

        scheduled = default_scheduled_jobs().get(job_type)
        cron_expr = scheduled.cron_expression if scheduled else None
        if cron_expr is None:
            return Err(GrowthAnalysisError(f"No cron expression for job type: {job_type}"))

        job = JobDefinition(
            job_id=f"rank-capture-{site_id}-{cadence}",
            job_type=job_type,
            payload={"site_id": site_id, "cadence": cadence},
            site_id=site_id,
        )
        return Ok(self._job_queue.schedule(job, cron_expr))

    def generate_report(
        self,
        site_id: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> Result[RankTrackingReport, GrowthAnalysisError]:
        snapshots_result = self._repo.get_snapshots(
            site_id=site_id,
            start_date=start_date,
            end_date=end_date,
        )
        if snapshots_result.is_err:
            return Err(GrowthAnalysisError(f"Failed to get snapshots: {snapshots_result.unwrap_err()}"))

        snapshots = snapshots_result.unwrap()
        report = RankTrackingReport(
            site_id=site_id,
            snapshot_count=len(snapshots),
            latest_snapshot_at=max((s.captured_at for s in snapshots), default=None),
            changes=self._detect_ranking_changes(snapshots),
            visibility_trend=self._compute_visibility_trend(snapshots),
            share_of_voice=self._compute_share_of_voice(site_id, snapshots),
            computed_at=datetime.now(timezone.utc),
            serp_features=self._compute_serp_features(snapshots),
            rank_distribution=self._compute_rank_distribution(snapshots),
        )
        return Ok(report)

    def _detect_ranking_changes(self, snapshots: list[RankingSnapshot]) -> list[RankingChange]:
        changes: list[RankingChange] = []
        by_keyword: dict[str, list[RankingSnapshot]] = {}
        for snap in snapshots:
            by_keyword.setdefault(snap.keyword_id, []).append(snap)

        for keyword_id, snaps in by_keyword.items():
            sorted_snaps = sorted(snaps, key=lambda s: s.captured_at)
            for index in range(1, len(sorted_snaps)):
                prev = sorted_snaps[index - 1]
                curr = sorted_snaps[index]
                if prev.position == curr.position:
                    continue
                if prev.position is None or curr.position is None:
                    change_val = 0
                    change_pct = None
                    significance = "major"
                else:
                    change_val = prev.position - curr.position
                    change_pct = (change_val / prev.position) * 100 if prev.position else None
                    significance = "major" if abs(change_val) >= 10 else "moderate" if abs(change_val) >= 5 else "minor"
                changes.append(RankingChange(
                    keyword_id=keyword_id,
                    keyword=curr.keyword,
                    page_id=curr.page_id,
                    previous_position=prev.position,
                    current_position=curr.position,
                    change=change_val,
                    change_percentage=change_pct,
                    detected_at=curr.captured_at,
                    significance=significance,
                ))
        return sorted(changes, key=lambda c: c.detected_at, reverse=True)[:50]

    def _compute_visibility_trend(self, snapshots: list[RankingSnapshot]) -> TimeSeriesExport:
        by_date: dict[str, list[int | None]] = {}
        for snap in snapshots:
            by_date.setdefault(snap.captured_at.date().isoformat(), []).append(snap.position)

        series = []
        for date_str, positions in sorted(by_date.items()):
            valid_positions = [p for p in positions if p is not None]
            avg_visibility = 0.0
            if valid_positions:
                avg_visibility = sum((101 - p) / 100 for p in valid_positions) / len(valid_positions)
            series.append({"date": date_str, "value": round(avg_visibility, 3)})

        return TimeSeriesExport(series=series, metric_name="visibility_score", aggregation="average")

    def _compute_share_of_voice(self, site_id: str, snapshots: list[RankingSnapshot]) -> float | None:
        """Reserved for M3 competitor-rank integration when real provider data exists."""
        return None

    def _compute_serp_features(self, snapshots: list[RankingSnapshot]) -> dict[str, int]:
        """Count SERP features owned across the latest snapshots (§1.3 SERP Features tab)."""
        features: dict[str, int] = {}
        for snap in snapshots:
            for ftype in getattr(snap, "serp_features", []) or []:
                name = ftype if isinstance(ftype, str) else getattr(ftype, "feature_type", None)
                if name:
                    features[name] = features.get(name, 0) + 1
        return features

    def _compute_rank_distribution(self, snapshots: list[RankingSnapshot]) -> dict[str, int]:
        """Bucket latest positions into rank bands (§1.3 Rank distribution bar)."""
        bands = {"1-3": 0, "4-10": 0, "11-20": 0, "21-50": 0, "51-100": 0}
        # Use only the most recent snapshot per keyword.
        latest: dict[str, RankingSnapshot] = {}
        for snap in snapshots:
            cur = latest.get(snap.keyword_id)
            if cur is None or snap.captured_at > cur.captured_at:
                latest[snap.keyword_id] = snap
        for snap in latest.values():
            pos = snap.position
            if pos is None:
                continue
            if pos <= 3:
                bands["1-3"] += 1
            elif pos <= 10:
                bands["4-10"] += 1
            elif pos <= 20:
                bands["11-20"] += 1
            elif pos <= 50:
                bands["21-50"] += 1
            else:
                bands["51-100"] += 1
        return bands