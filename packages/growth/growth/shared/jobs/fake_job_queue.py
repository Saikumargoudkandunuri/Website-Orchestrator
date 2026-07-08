"""In-process, synchronous FakeJobQueue for tests (§7).

No test should depend on real scheduling infrastructure. The FakeJobQueue
executes jobs synchronously in-process, records them for assertion, and can
be configured to fail specific job types for error-path testing.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable

from growth.shared.jobs.job_queue_interface import (
    JobDefinition,
    JobResult,
    JobStatus,
)

__all__ = ["FakeJobQueue"]


class FakeJobQueue:
    """Synchronous, in-process test double for JobQueue."""

    def __init__(self, fail_job_types: set[str] | None = None) -> None:
        self._fail_types = fail_job_types or set()
        self._jobs: dict[str, JobResult] = {}
        self._handlers: dict[str, Callable[[JobDefinition], dict]] = {}
        # Recorded for test assertions
        self.enqueued: list[JobDefinition] = []
        self.scheduled: list[tuple[JobDefinition, str]] = []

    def register_handler(
        self, job_type: str, handler: Callable[[JobDefinition], dict]
    ) -> None:
        """Register a handler function for a job_type (for synchronous execution)."""
        self._handlers[job_type] = handler

    def enqueue(self, job: JobDefinition) -> str:
        """Execute the job synchronously (for tests) and record the result."""
        self.enqueued.append(job)
        now = datetime.now(timezone.utc)

        if job.job_type in self._fail_types:
            result = JobResult(
                job_id=job.job_id,
                job_type=job.job_type,
                status=JobStatus.FAILED,
                started_at=now,
                completed_at=now,
                error_message=f"Forced failure for job_type {job.job_type!r}",
            )
        elif job.job_type in self._handlers:
            try:
                output = self._handlers[job.job_type](job)
                result = JobResult(
                    job_id=job.job_id,
                    job_type=job.job_type,
                    status=JobStatus.COMPLETED,
                    started_at=now,
                    completed_at=datetime.now(timezone.utc),
                    output=output,
                )
            except Exception as exc:
                result = JobResult(
                    job_id=job.job_id,
                    job_type=job.job_type,
                    status=JobStatus.FAILED,
                    started_at=now,
                    completed_at=datetime.now(timezone.utc),
                    error_message=str(exc),
                )
        else:
            # No handler registered — mark as completed with empty output
            result = JobResult(
                job_id=job.job_id,
                job_type=job.job_type,
                status=JobStatus.COMPLETED,
                started_at=now,
                completed_at=now,
                output={},
            )

        self._jobs[job.job_id] = result
        return job.job_id

    def schedule(self, job: JobDefinition, cron_expression: str) -> str:
        """Record a scheduled job (no real scheduling in tests)."""
        self.scheduled.append((job, cron_expression))
        result = JobResult(
            job_id=job.job_id,
            job_type=job.job_type,
            status=JobStatus.SCHEDULED,
        )
        self._jobs[job.job_id] = result
        return job.job_id

    def status(self, job_id: str) -> JobResult | None:
        return self._jobs.get(job_id)

    def cancel(self, job_id: str) -> bool:
        if job_id in self._jobs:
            del self._jobs[job_id]
            return True
        return False
