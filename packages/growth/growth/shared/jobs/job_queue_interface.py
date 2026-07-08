"""Background job/worker abstraction (§7).

The JobQueue interface is implementation-agnostic — it does not hardcode Celery,
RQ, or any cloud provider. Tests use the FakeJobQueue (synchronous, in-process).
Production can adapt to whatever async task mechanism the stack provides.

All jobs must be:
1. Idempotent — re-running a missed job for the same period must not
   double-insert records.
2. Event-emitting — emit a DomainEvent on completion/failure so the Automation
   Engine can react to job outcomes.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Callable, Protocol, runtime_checkable

from pydantic import BaseModel, Field

__all__ = [
    "JobStatus",
    "JobDefinition",
    "JobResult",
    "JobQueue",
]


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SCHEDULED = "scheduled"


class JobDefinition(BaseModel):
    """A unit of background work."""

    job_id: str
    job_type: str  # e.g. "rank_tracking_capture", "report_generation", "analytics_snapshot"
    payload: dict[str, Any] = Field(default_factory=dict)
    tenant_id: str = ""
    organization_id: str | None = None
    site_id: str | None = None
    cron_expression: str | None = None  # If set, this is a recurring scheduled job
    idempotency_key: str | None = None  # prevents duplicate execution
    created_at: datetime | None = None


class JobResult(BaseModel):
    """The result of a job execution."""

    job_id: str
    job_type: str
    status: JobStatus
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None
    output: dict[str, Any] = Field(default_factory=dict)


@runtime_checkable
class JobQueue(Protocol):
    """Minimal background job/worker abstraction (§7).

    Implementation-agnostic: do not hardcode Celery/RQ in business logic.
    """

    def enqueue(self, job: JobDefinition) -> str:
        """Enqueue a job for immediate execution. Returns the job_id."""
        ...

    def schedule(self, job: JobDefinition, cron_expression: str) -> str:
        """Schedule a recurring job. Returns the job_id."""
        ...

    def status(self, job_id: str) -> JobResult | None:
        """Return the current status of a job, or None if not found."""
        ...

    def cancel(self, job_id: str) -> bool:
        """Cancel a pending/scheduled job. Returns True if cancelled."""
        ...
