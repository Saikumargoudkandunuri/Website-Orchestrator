"""Scheduled job registry — maps job types to their cron expressions and handlers.

Jobs needed this milestone (§7):
- Rank Tracking capture (daily/weekly/monthly cadence per site config)
- Scheduled Reporting generation
- Analytics snapshot capture
- Automation Engine event-processing loop (if async)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from growth.shared.jobs.job_queue_interface import JobDefinition, JobQueue

__all__ = ["ScheduledJobDefinition", "ScheduledJobRegistry"]


@dataclass
class ScheduledJobDefinition:
    """A registered scheduled job definition."""

    job_type: str
    cron_expression: str
    description: str = ""
    handler: Callable[[JobDefinition], dict] | None = None


class ScheduledJobRegistry:
    """Registry of scheduled jobs and their cron expressions.

    Used by the composition root to register all recurring jobs at startup.
    """

    def __init__(self) -> None:
        self._jobs: dict[str, ScheduledJobDefinition] = {}

    def register(self, job_def: ScheduledJobDefinition) -> None:
        """Register a scheduled job definition."""
        self._jobs[job_def.job_type] = job_def

    def get(self, job_type: str) -> ScheduledJobDefinition | None:
        return self._jobs.get(job_type)

    def all_jobs(self) -> list[ScheduledJobDefinition]:
        return list(self._jobs.values())

    def schedule_all(self, queue: JobQueue, tenant_id: str, site_id: str) -> list[str]:
        """Schedule all registered jobs on the given queue. Returns job_ids."""
        import uuid

        job_ids = []
        for job_def in self._jobs.values():
            job = JobDefinition(
                job_id=uuid.uuid4().hex,
                job_type=job_def.job_type,
                payload={},
                tenant_id=tenant_id,
                site_id=site_id,
                cron_expression=job_def.cron_expression,
            )
            job_id = queue.schedule(job, job_def.cron_expression)
            job_ids.append(job_id)
        return job_ids


def default_scheduled_jobs() -> ScheduledJobRegistry:
    """Return the default registry with all Milestone 4 scheduled jobs."""
    registry = ScheduledJobRegistry()
    registry.register(ScheduledJobDefinition(
        job_type="rank_tracking_capture_daily",
        cron_expression="0 3 * * *",
        description="Daily rank tracking capture for all tracked keywords.",
    ))
    registry.register(ScheduledJobDefinition(
        job_type="rank_tracking_capture_weekly",
        cron_expression="0 4 * * 1",
        description="Weekly rank tracking capture.",
    ))
    registry.register(ScheduledJobDefinition(
        job_type="rank_tracking_capture_monthly",
        cron_expression="0 5 1 * *",
        description="Monthly rank tracking capture.",
    ))
    registry.register(ScheduledJobDefinition(
        job_type="analytics_snapshot_capture",
        cron_expression="0 2 * * *",
        description="Daily analytics snapshot capture.",
    ))
    registry.register(ScheduledJobDefinition(
        job_type="scheduled_report_generation",
        cron_expression="0 6 * * 1",
        description="Weekly scheduled report generation.",
    ))
    return registry