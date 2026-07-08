"""Smoke / interface tests for the API_Surface (task 13.10).

These are conventional example-based tests (not property-based) that pin down
two cross-cutting guarantees of the FastAPI application:

* **Automatic OpenAPI documentation (Req 10.9).** ``GET /docs`` returns ``200``
  and the generated ``/openapi.json`` schema advertises every endpoint of the
  loop: ``/crawl``, ``/issues``, ``/fixes``, ``/audit-log``, and the three
  decision endpoints ``/fixes/{id}/approve|reject|rollback``.
* **Thin route handlers (Req 10.10).** The decision handlers delegate to the
  Governance_Layer and embed no business logic. Using a ``RecordingGovernance``
  fake that records each call and returns a pre-built record, each of
  approve/reject/rollback is invoked once against a *persisted* fix (so the
  not-found pre-check passes) and we assert the corresponding governance method
  was called **exactly once** with the ``(tenant, fix_id, actor, rationale)``
  taken verbatim from the request, and that the handler returned the record the
  Governance_Layer produced without any extra transformation.

The tests are network-free: the Digital_Twin is a real
:class:`~digital_twin.repository.DigitalTwinRepository` on in-memory SQLite and
the remaining subsystems are minimal fakes (mirroring
``test_app_decisions.py``), so no live WordPress site or PostgreSQL is touched.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from check_engine import CheckEngine
from digital_twin.models import Base
from digital_twin.repository import DigitalTwinRepository
from fix_generator import FixGenerator

from core.types import (
    FixStatus,
    FixType,
    SuggestedFix,
    TargetRef,
)

from api import create_app

TENANT = "tenant-a"


# --- Fakes --------------------------------------------------------------------


class FakeCrawler:
    """A CrawlerPort fake; never invoked by these tests."""

    def crawl_site(self, start_url: str, max_pages: int):  # pragma: no cover
        raise NotImplementedError

    def check_link_status(self, url: str):  # pragma: no cover
        raise NotImplementedError


class RecordingGovernance:
    """A GovernancePort fake that records each decision call and returns a
    pre-built updated fix.

    Recording the full ``(tenant_id, fix_id, actor, rationale)`` tuple lets the
    tests assert the handler delegated exactly once with the request arguments,
    and returning ``_result`` unchanged lets them assert the handler surfaced the
    Governance_Layer's record without transformation (Req 10.10).
    """

    def __init__(self, result: SuggestedFix) -> None:
        self._result = result
        self.calls: list[tuple[str, str, str, str, str]] = []

    def list_pending_fixes(self, tenant_id: str):  # pragma: no cover - unused
        return []

    def approve_fix(self, tenant_id, fix_id, actor, rationale) -> SuggestedFix:
        self.calls.append(("approve_fix", tenant_id, fix_id, actor, rationale))
        return self._result

    def reject_fix(self, tenant_id, fix_id, actor, rationale) -> SuggestedFix:
        self.calls.append(("reject_fix", tenant_id, fix_id, actor, rationale))
        return self._result

    def rollback_fix(self, tenant_id, fix_id, actor, rationale) -> SuggestedFix:
        self.calls.append(("rollback_fix", tenant_id, fix_id, actor, rationale))
        return self._result


# --- App builders -------------------------------------------------------------


def _make_repo() -> DigitalTwinRepository:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    return DigitalTwinRepository(session_factory, tenant_id=TENANT)


def _build_app(repo: DigitalTwinRepository, governance):
    return create_app(
        crawler=FakeCrawler(),
        digital_twin=repo,
        check_engine=CheckEngine(),
        fix_generator=FixGenerator(),
        governance=governance,
        tenant_id=TENANT,
    )


def _seed_fix(fix_id: str = "fix-1") -> SuggestedFix:
    """A persisted pending fix so the decision not-found pre-check passes."""
    return SuggestedFix(
        id=fix_id,
        tenant_id=TENANT,
        issue_id="issue-1",
        fix_type=FixType.UPDATE_ALT_TEXT,
        auto_applicable=1,
        target_ref=TargetRef(media_id=123),
        proposed_value="A red bike",
        status=FixStatus.PENDING,
    )


# --- OpenAPI documentation (Req 10.9) -----------------------------------------


def test_docs_endpoint_returns_200() -> None:
    client = TestClient(_build_app(_make_repo(), RecordingGovernance(_seed_fix())))

    response = client.get("/docs")

    assert response.status_code == 200


def test_openapi_schema_advertises_all_loop_endpoints() -> None:
    client = TestClient(_build_app(_make_repo(), RecordingGovernance(_seed_fix())))

    response = client.get("/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    for expected in (
        "/crawl",
        "/issues",
        "/fixes",
        "/audit-log",
        "/fixes/{id}/approve",
        "/fixes/{id}/reject",
        "/fixes/{id}/rollback",
    ):
        assert expected in paths, f"OpenAPI schema is missing {expected!r}"


# --- Thin decision handlers delegate exactly once (Req 10.10) -----------------


@pytest.mark.parametrize(
    ("verb", "method"),
    [
        ("approve", "approve_fix"),
        ("reject", "reject_fix"),
        ("rollback", "rollback_fix"),
    ],
)
def test_decision_handler_delegates_exactly_once_to_governance(
    verb: str, method: str
) -> None:
    repo = _make_repo()
    repo.persist_fixes(TENANT, [_seed_fix("fix-1")])
    # The record the Governance_Layer would return for the decision.
    produced = _seed_fix("fix-1").model_copy(
        update={"status": FixStatus.APPROVED}
    )
    governance = RecordingGovernance(produced)
    client = TestClient(_build_app(repo, governance))

    response = client.post(
        f"/fixes/fix-1/{verb}",
        json={"actor": "alice", "rationale": "because reasons"},
    )

    assert response.status_code == 200
    # Delegated exactly once, to the matching governance method, with the
    # tenant + path id + request body passed straight through (no business
    # logic in the handler).
    assert governance.calls == [
        (method, TENANT, "fix-1", "alice", "because reasons")
    ]
    # The handler returned the Governance_Layer's record unchanged.
    assert response.json() == produced.model_dump(mode="json")
