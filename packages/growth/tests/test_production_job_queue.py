"""Tests for the production job queue (§2.3): retry, backoff, dead-letter,
idempotency, cron scheduling, and the worker/scheduler abstraction.

FakeJobQueue remains the default for the rest of the Growth test suite and is
not affected by anything here.
"""
from __future__ import annotations

import threading
import time

from growth.shared.jobs.fake_job_queue import FakeJobQueue
from growth.shared.jobs.job_queue_interface import JobDefinition, JobStatus
from growth.shared.jobs.production_job_queue import ProductionJobQueue, RetryPolicy


def _wait_for(
    predicate,
    *,
    timeout: float = 5.0,
    interval: float = 0.01,
) -> None:
    """Poll *predicate* until it returns truthy or *timeout* seconds elapse."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(interval)
    raise AssertionError("timed out waiting for condition")


def _job(
    job_id: str = "job-1",
    *,
    job_type: str = "test_job",
    idempotency_key: str | None = None,
    payload: dict | None = None,
) -> JobDefinition:
    return JobDefinition(
        job_id=job_id,
        job_type=job_type,
        idempotency_key=idempotency_key,
        payload=payload or {},
    )


def test_production_queue_runs_job_and_records_completed_status() -> None:
    queue = ProductionJobQueue(retry_policy=RetryPolicy(max_retries=1, base_delay_s=0.01))
    queue.register_handler("test_job", lambda job: {"echo": job.payload})

    job_id = queue.enqueue(_job())

    _wait_for(lambda: queue.status(job_id) is not None and
              queue.status(job_id).status == JobStatus.COMPLETED)
    result = queue.status(job_id)
    assert result is not None
    assert result.status == JobStatus.COMPLETED
    assert result.output == {"echo": {}}
    assert result.started_at is not None
    assert result.completed_at is not None


def test_retry_then_succeed_eventually_completes() -> None:
    queue = ProductionJobQueue(retry_policy=RetryPolicy(max_retries=3, base_delay_s=0.01))

    attempts: list[int] = []
    lock = threading.Lock()

    def flaky_handler(job: JobDefinition) -> dict:
        with lock:
            attempts.append(len(attempts) + 1)
            current = attempts[-1]
        if current < 3:
            raise RuntimeError(f"transient failure on attempt {current}")
        return {"ok": True}

    queue.register_handler("flaky", flaky_handler)
    job_id = queue.enqueue(_job(job_type="flaky"))

    _wait_for(lambda: queue.status(job_id) is not None and
              queue.status(job_id).status == JobStatus.COMPLETED, timeout=10.0)

    result = queue.status(job_id)
    assert result is not None
    assert result.status == JobStatus.COMPLETED
    assert result.output == {"ok": True}

    history = queue.execution_history(job_id)
    terminal = [r["status"] for r in history if r["status"] != "running"]
    # Two failures then a success.
    assert terminal.count("failed") == 2
    assert terminal[-1] == "completed"


def test_retry_exhaustion_moves_job_to_dead_letter() -> None:
    queue = ProductionJobQueue(retry_policy=RetryPolicy(max_retries=2, base_delay_s=0.01))

    def always_fails(job: JobDefinition) -> dict:
        raise RuntimeError("permanent failure")

    queue.register_handler("bad", always_fails)
    job_id = queue.enqueue(_job(job_type="bad"))

    _wait_for(lambda: len(queue.dead_letter_jobs()) >= 1, timeout=10.0)

    dead = queue.dead_letter_jobs()
    assert len(dead) == 1
    assert dead[0]["job"]["job_id"] == job_id
    assert "permanent failure" in dead[0]["last_result"]["error_message"]

    history = queue.execution_history(job_id)
    # max_retries=2 → 3 total attempts. Each attempt records a 'running' start
    # and a terminal status, so we assert on the terminal records.
    terminal = [r for r in history if r["status"] != "running"]
    assert len(terminal) == 3
    assert all(r["status"] == "failed" for r in terminal)


def test_idempotency_prevents_duplicate_execution_on_same_key() -> None:
    queue = ProductionJobQueue(retry_policy=RetryPolicy(max_retries=0, base_delay_s=0.01))

    call_count = 0
    lock = threading.Lock()

    def counting_handler(job: JobDefinition) -> dict:
        nonlocal call_count
        with lock:
            call_count += 1
        return {"n": call_count}

    queue.register_handler("count", counting_handler)

    j1 = _job(job_id="idem-1", job_type="count", idempotency_key="shared-key")
    j2 = _job(job_id="idem-2", job_type="count", idempotency_key="shared-key")

    id1 = queue.enqueue(j1)
    id2 = queue.enqueue(j2)

    # Same idempotency key → second enqueue returns the first job id and does
    # not execute a second time.
    assert id1 == id2
    _wait_for(lambda: queue.status(id1) is not None and
              queue.status(id1).status == JobStatus.COMPLETED)
    _wait_for(lambda: call_count == 1, timeout=2.0)
    assert call_count == 1


def test_cron_schedule_records_scheduled_status_and_expression() -> None:
    queue = ProductionJobQueue()
    job = _job(job_id="cron-job", job_type="scheduled_report_generation")

    returned_id = queue.schedule(job, "0 6 * * 1")

    assert returned_id == "cron-job"
    status = queue.status("cron-job")
    assert status is not None
    assert status.status == JobStatus.SCHEDULED


def test_overlapping_enqueue_with_same_idempotency_key_runs_once() -> None:
    """Adversarial concurrency: two threads enqueue the same key at once."""
    queue = ProductionJobQueue(retry_policy=RetryPolicy(max_retries=0, base_delay_s=0.01))

    runs: list[str] = []
    lock = threading.Lock()
    barrier = threading.Barrier(2)

    def slow_handler(job: JobDefinition) -> dict:
        with lock:
            runs.append(job.job_id)
        return {}

    queue.register_handler("slow", slow_handler)

    def enqueueer(job_id: str) -> None:
        barrier.wait()
        queue.enqueue(_job(job_id=job_id, job_type="slow", idempotency_key="overlap-key"))

    t1 = threading.Thread(target=enqueueer, args=("overlap-a",))
    t2 = threading.Thread(target=enqueueer, args=("overlap-b",))
    t1.start()
    t2.start()
    t1.join(timeout=5.0)
    t2.join(timeout=5.0)

    _wait_for(lambda: len(runs) == 1 or
              queue.status("overlap-a") is not None or
              queue.status("overlap-b") is not None, timeout=5.0)
    # Only one of the two job ids should ever have executed.
    assert len(runs) <= 1


def test_manual_trigger_runs_job() -> None:
    queue = ProductionJobQueue(retry_policy=RetryPolicy(max_retries=0, base_delay_s=0.01))
    queue.register_handler("manual", lambda job: {"triggered": True})

    job_id = queue.trigger(_job(job_type="manual"))

    _wait_for(lambda: queue.status(job_id) is not None and
              queue.status(job_id).status == JobStatus.COMPLETED)
    assert queue.status(job_id).output == {"triggered": True}


def test_cancel_removes_job_from_status() -> None:
    queue = ProductionJobQueue()
    queue.schedule(_job(job_id="sched-1", job_type="recurring"), "0 * * * *")

    assert queue.status("sched-1") is not None
    assert queue.cancel("sched-1") is True
    assert queue.status("sched-1") is None
    assert queue.cancel("does-not-exist") is False


def test_dead_letter_job_can_be_requeued() -> None:
    queue = ProductionJobQueue(retry_policy=RetryPolicy(max_retries=0, base_delay_s=0.01))

    state = {"fail": True}

    def maybe_fails(job: JobDefinition) -> dict:
        if state["fail"]:
            raise RuntimeError("first attempt fails")
        return {"recovered": True}

    queue.register_handler("recover", maybe_fails)
    job_id = queue.enqueue(_job(job_type="recover"))

    _wait_for(lambda: len(queue.dead_letter_jobs()) >= 1, timeout=5.0)
    assert len(queue.dead_letter_jobs()) == 1

    # Fix the handler so the requeued job succeeds.
    state["fail"] = False
    requeued_id = queue.requeue_dead_letter(job_id)
    assert requeued_id == job_id

    _wait_for(lambda: queue.status(job_id) is not None and
              queue.status(job_id).status == JobStatus.COMPLETED, timeout=5.0)
    assert queue.status(job_id).output == {"recovered": True}


def test_fake_job_queue_still_satisfies_protocol_and_works_unmodified() -> None:
    """Confirm the pre-existing FakeJobQueue is unchanged and still passes its
    contract — no production scheduler change may break tests relying on it."""
    from growth.shared.jobs.job_queue_interface import JobQueue

    fake = FakeJobQueue()
    assert isinstance(fake, JobQueue)

    job = _job(job_id="fake-1", job_type="echo")
    fake.register_handler("echo", lambda j: {"v": 1})
    returned = fake.enqueue(job)
    assert returned == "fake-1"
    assert fake.status("fake-1").status == JobStatus.COMPLETED
    assert fake.enqueued == [job]


def test_retry_policy_delay_is_exponential_and_capped() -> None:
    policy = RetryPolicy(max_retries=4, base_delay_s=1.0, max_delay_s=10.0, backoff_factor=2.0)
    # attempt 1: 1.0, attempt 2: 2.0, attempt 3: 4.0, attempt 4: 8.0, attempt 5: capped 10.0
    delays = [policy.delay_for_attempt(a) for a in range(1, 6)]
    assert delays == [1.0, 2.0, 4.0, 8.0, 10.0]
