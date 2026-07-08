"""Production in-process job queue with retry, backoff, dead-letter, and history.

This is a real implementation of the JobQueue protocol suitable for single-process
deployments.  It uses ``threading`` for background execution, an in-memory dead-letter
queue for exhausted retries, and a configurable retry policy with exponential
backoff.  It is intentionally vendor-agnostic: no Celery, RQ, Redis, or external
broker is required.  For clustered/multi-process deployments the operator can swap
in a broker-backed JobQueue implementation behind the same protocol.

FakeJobQueue remains the default for tests and continues to work unmodified.
"""
from __future__ import annotations

import hashlib
import logging
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from growth.shared.jobs.job_queue_interface import (
    JobDefinition,
    JobQueue,
    JobResult,
    JobStatus,
)

__all__ = [
    "ProductionJobQueue",
    "RetryPolicy",
    "JobExecutionRecord",
]

logger = logging.getLogger(__name__)


class RetryPolicy:
    """Configurable retry behaviour for failed jobs."""

    def __init__(
        self,
        *,
        max_retries: int = 3,
        base_delay_s: float = 1.0,
        max_delay_s: float = 60.0,
        backoff_factor: float = 2.0,
    ) -> None:
        self.max_retries = max_retries
        self.base_delay_s = base_delay_s
        self.max_delay_s = max_delay_s
        self.backoff_factor = backoff_factor

    def delay_for_attempt(self, attempt: int) -> float:
        """Return the delay in seconds before *attempt* (1-indexed)."""
        delay = self.base_delay_s * (self.backoff_factor ** (attempt - 1))
        return min(delay, self.max_delay_s)


class JobExecutionRecord:
    """Persisted execution history for a single job run."""

    __slots__ = (
        "job_id",
        "attempt",
        "status",
        "started_at",
        "completed_at",
        "error_message",
    )

    def __init__(
        self,
        *,
        job_id: str,
        attempt: int,
        status: JobStatus,
        started_at: datetime,
        completed_at: datetime | None = None,
        error_message: str | None = None,
    ) -> None:
        self.job_id = job_id
        self.attempt = attempt
        self.status = status
        self.started_at = started_at
        self.completed_at = completed_at
        self.error_message = error_message

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "attempt": self.attempt,
            "status": self.status.value,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error_message": self.error_message,
        }


class ProductionJobQueue:
    """In-process production job queue with retry, dead-letter, and history.

    Implements the :class:`~growth.shared.jobs.job_queue_interface.JobQueue`
    protocol.  Jobs execute in daemon threads so they do not block the caller.
    Retry is automatic with exponential backoff up to ``RetryPolicy.max_retries``.
    Exhausted jobs are moved to a dead-letter queue and can be inspected or
    re-enqueued manually.
    """

    def __init__(
        self,
        *,
        retry_policy: RetryPolicy | None = None,
        handlers: dict[str, Callable[[JobDefinition], dict[str, Any]]] | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self._retry = retry_policy or RetryPolicy()
        self._handlers = dict(handlers or {})
        self._clock = clock or time.monotonic
        self._lock = threading.Lock()
        # job_id → current status/result
        self._results: dict[str, JobResult] = {}
        # idempotency_key → job_id (prevent duplicate enqueue)
        self._idempotency: dict[str, str] = {}
        # job_id → list of execution records
        self._history: dict[str, list[JobExecutionRecord]] = {}
        # dead-letter: job_id → (JobDefinition, last_result)
        self._dead_letter: dict[str, tuple[JobDefinition, JobResult]] = {}
        # scheduled: job_id → (JobDefinition, cron_expression)
        self._scheduled: dict[str, tuple[JobDefinition, str]] = {}
        # manual trigger support
        self._manual_event = threading.Event()

    # -- public interface -------------------------------------------------------

    def register_handler(
        self, job_type: str, handler: Callable[[JobDefinition], dict[str, Any]]
    ) -> None:
        """Register a handler for a job type."""
        self._handlers[job_type] = handler

    def enqueue(self, job: JobDefinition) -> str:
        """Enqueue a job for immediate (async) execution with retry."""
        # Idempotency guard
        if job.idempotency_key:
            with self._lock:
                existing = self._idempotency.get(job.idempotency_key)
                if existing:
                    return existing

        self._mark_status(job.job_id, JobStatus.PENDING)
        if job.idempotency_key:
            with self._lock:
                self._idempotency[job.idempotency_key] = job.job_id

        thread = threading.Thread(
            target=self._execute_with_retry,
            args=(job,),
            daemon=True,
            name=f"job-{job.job_id}",
        )
        thread.start()
        return job.job_id

    def schedule(self, job: JobDefinition, cron_expression: str) -> str:
        """Record a recurring scheduled job (cron expression stored for future use).

        The cron expression is stored but not actively fired by this implementation.
        The scheduler lifecycle (parsing cron, ticking) is the responsibility of
        the owning service.  This keeps the queue focused on execution semantics.
        """
        self._mark_status(job.job_id, JobStatus.SCHEDULED)
        with self._lock:
            self._scheduled[job.job_id] = (job, cron_expression)
        return job.job_id

    def status(self, job_id: str) -> JobResult | None:
        with self._lock:
            return self._results.get(job_id)

    def cancel(self, job_id: str) -> bool:
        with self._lock:
            if job_id in self._results:
                del self._results[job_id]
                self._scheduled.pop(job_id, None)
                return True
        return False

    # -- manual trigger ----------------------------------------------------------

    def trigger(self, job: JobDefinition) -> str:
        """Manually trigger a job (on-demand endpoint-triggered)."""
        return self.enqueue(job)

    # -- inspection --------------------------------------------------------------

    def execution_history(self, job_id: str) -> list[dict[str, Any]]:
        """Return execution history for a job."""
        with self._lock:
            records = self._history.get(job_id, [])
        return [r.to_dict() for r in records]

    def dead_letter_jobs(self) -> list[dict[str, Any]]:
        """Return all dead-lettered jobs."""
        with self._lock:
            items = list(self._dead_letter.values())
        return [
            {"job": job.model_dump(), "last_result": result.model_dump()}
            for job, result in items
        ]

    def requeue_dead_letter(self, job_id: str) -> str | None:
        """Re-enqueue a dead-lettered job for another retry cycle."""
        with self._lock:
            entry = self._dead_letter.pop(job_id, None)
        if entry is None:
            return None
        job, _ = entry
        return self.enqueue(job)

    # -- internal ----------------------------------------------------------------

    def _mark_status(self, job_id: str, status: JobStatus) -> None:
        result = JobResult(
            job_id=job_id,
            job_type="",
            status=status,
        )
        with self._lock:
            self._results[job_id] = result

    def _execute_with_retry(self, job: JobDefinition) -> None:
        max_attempts = self._retry.max_retries + 1
        last_result: JobResult | None = None

        for attempt in range(1, max_attempts + 1):
            started = datetime.now(timezone.utc)
            record = JobExecutionRecord(
                job_id=job.job_id,
                attempt=attempt,
                status=JobStatus.RUNNING,
                started_at=started,
            )
            self._append_history(record)

            self._mark_status(job.job_id, JobStatus.RUNNING)
            handler = self._handlers.get(job.job_type)

            try:
                if handler is not None:
                    output = handler(job)
                else:
                    output = {}
                completed = datetime.now(timezone.utc)
                result = JobResult(
                    job_id=job.job_id,
                    job_type=job.job_type,
                    status=JobStatus.COMPLETED,
                    started_at=started,
                    completed_at=completed,
                    output=output,
                )
                self._store_result(job.job_id, result)
                self._append_history(JobExecutionRecord(
                    job_id=job.job_id,
                    attempt=attempt,
                    status=JobStatus.COMPLETED,
                    started_at=started,
                    completed_at=completed,
                ))
                logger.info(
                    "job_completed",
                    extra={
                        "job_id": job.job_id,
                        "job_type": job.job_type,
                        "attempt": attempt,
                        "tenant_id": job.tenant_id,
                    },
                )
                return
            except Exception as exc:
                completed = datetime.now(timezone.utc)
                error_msg = f"{type(exc).__name__}: {exc}"
                result = JobResult(
                    job_id=job.job_id,
                    job_type=job.job_type,
                    status=JobStatus.FAILED,
                    started_at=started,
                    completed_at=completed,
                    error_message=error_msg,
                )
                self._store_result(job.job_id, result)
                self._append_history(JobExecutionRecord(
                    job_id=job.job_id,
                    attempt=attempt,
                    status=JobStatus.FAILED,
                    started_at=started,
                    completed_at=completed,
                    error_message=error_msg,
                ))
                last_result = result
                logger.warning(
                    "job_failed",
                    extra={
                        "job_id": job.job_id,
                        "job_type": job.job_type,
                        "attempt": attempt,
                        "max_attempts": max_attempts,
                        "error": error_msg,
                        "tenant_id": job.tenant_id,
                    },
                )
                if attempt < max_attempts:
                    delay = self._retry.delay_for_attempt(attempt)
                    time.sleep(delay)

        # All retries exhausted → dead letter
        with self._lock:
            self._dead_letter[job.job_id] = (job, last_result)
        logger.error(
            "job_dead_lettered",
            extra={
                "job_id": job.job_id,
                "job_type": job.job_type,
                "tenant_id": job.tenant_id,
                "error": last_result.error_message if last_result else None,
            },
        )

    def _store_result(self, job_id: str, result: JobResult) -> None:
        with self._lock:
            self._results[job_id] = result

    def _append_history(self, record: JobExecutionRecord) -> None:
        with self._lock:
            self._history.setdefault(record.job_id, []).append(record)
