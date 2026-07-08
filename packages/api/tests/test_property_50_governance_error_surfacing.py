"""Property 50 — Governance errors surface as failures, never as success.

Feature: website-orchestrator-milestone-0, Property 50: Governance errors surface
as failures, never as success.

**Validates: Requirements 10.13**

Requirement 10.13 says every Governance_Layer (and Publishing_Adapter) failure
raised while deciding a fix must surface through the decision endpoints as an
explicit HTTP *failure* carrying the reason — and never as a ``2xx`` success.

This is a Hypothesis property test (>= 100 examples, per the workspace default
profile). It exercises the universal claim across:

* every decision verb (``approve`` / ``reject`` / ``rollback``),
* every ``GovernanceError`` subclass the Governance_Layer may raise
  (``FixNotFoundError``, ``FixAlreadyDecidedError``, ``InvalidDecisionError``,
  ``BeforeReadError``, ``RollbackNotAllowedError``) plus the ``GovernanceError``
  base itself, and
* a ``PublishingError`` subclass (``WPClientError``) raised while applying the
  decision,
* over arbitrary valid actor/rationale bodies.

The app is built network-free: an in-memory SQLite Digital_Twin repository
seeded with the target fix (so the endpoint's not-found pre-check passes and the
request reaches governance), a ``RaisingGovernance`` fake whose decision methods
always raise the generated exception, and minimal inert fakes for the other
subsystems. For each generated case we assert the response is a non-2xx failure
whose body carries a non-empty reason, and that the status matches the exact
mapping the API defines per exception type.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from hypothesis import given, settings
from hypothesis import strategies as st
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from check_engine import CheckEngine
from digital_twin.models import Base
from digital_twin.repository import DigitalTwinRepository
from fix_generator import FixGenerator

from core.exceptions import (
    BeforeReadError,
    FixAlreadyDecidedError,
    FixNotFoundError,
    GovernanceError,
    InvalidDecisionError,
    RollbackNotAllowedError,
    WPClientError,
)
from core.types import FixStatus, FixType, SuggestedFix

from api import create_app

TENANT = "tenant-a"
FIX_ID = "fix-under-decision"


# --- Exception space under test ----------------------------------------------
#
# Each entry pairs an exception TYPE the Governance_Layer may raise on a decision
# with the exact HTTP status the API_Surface is required to report for it
# (Req 10.13). ``FixNotFoundError`` -> 404; ``FixAlreadyDecidedError`` /
# ``RollbackNotAllowedError`` -> 409; ``InvalidDecisionError`` -> 422; the
# ``BeforeReadError`` fail-closed case, the ``GovernanceError`` base, and any
# ``PublishingError`` (here ``WPClientError``) -> 502.
_EXCEPTION_STATUS: list[tuple[type[Exception], int]] = [
    (FixNotFoundError, 404),
    (FixAlreadyDecidedError, 409),
    (RollbackNotAllowedError, 409),
    (InvalidDecisionError, 422),
    (BeforeReadError, 502),
    (GovernanceError, 502),
    (WPClientError, 502),
]


# --- Fakes --------------------------------------------------------------------


class InertCrawler:
    """A CrawlerPort fake; never invoked by the decision endpoints."""

    def crawl_site(self, start_url: str, max_pages: int):  # pragma: no cover
        raise NotImplementedError

    def check_link_status(self, url: str):  # pragma: no cover
        raise NotImplementedError


class RaisingGovernance:
    """A GovernancePort fake whose every decision method raises a chosen error.

    Models a Governance_Layer that fails on the decision (for any reason in the
    error contract). The endpoint must map the raised error to a non-2xx
    failure, never a success (Req 10.13).
    """

    def __init__(self, exc: Exception) -> None:
        self._exc = exc
        self.calls: list[tuple[str, str, str, str]] = []

    def list_pending_fixes(self, tenant_id: str):  # pragma: no cover - unused
        return []

    def approve_fix(self, tenant_id, fix_id, actor, rationale) -> SuggestedFix:
        self.calls.append(("approve_fix", fix_id, actor, rationale))
        raise self._exc

    def reject_fix(self, tenant_id, fix_id, actor, rationale) -> SuggestedFix:
        self.calls.append(("reject_fix", fix_id, actor, rationale))
        raise self._exc

    def rollback_fix(self, tenant_id, fix_id, actor, rationale) -> SuggestedFix:
        self.calls.append(("rollback_fix", fix_id, actor, rationale))
        raise self._exc


# --- App builder --------------------------------------------------------------


def _seeded_client(governance: RaisingGovernance) -> TestClient:
    """Build the app with a repo seeded with the target fix + a raising fake.

    The fix is persisted so the endpoint's not-found pre-check (Req 10.12)
    passes and the request reaches the Governance_Layer, where the generated
    error is raised.
    """
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    repo = DigitalTwinRepository(session_factory, tenant_id=TENANT)
    repo.persist_fixes(
        TENANT,
        [
            SuggestedFix(
                id=FIX_ID,
                tenant_id=TENANT,
                issue_id="issue-1",
                fix_type=FixType.UPDATE_PAGE_CONTENT,
                auto_applicable=0,
                reason="Report only",
                status=FixStatus.PENDING,
            )
        ],
    )
    app = create_app(
        crawler=InertCrawler(),
        digital_twin=repo,
        check_engine=CheckEngine(),
        fix_generator=FixGenerator(),
        governance=governance,
        tenant_id=TENANT,
    )
    return TestClient(app)


# --- Strategies ---------------------------------------------------------------

# A non-blank field: contains at least one non-whitespace character so it passes
# the DecisionRequest boundary validation and actually reaches the governance
# call (otherwise a 422 would fire before governance is invoked).
_nonblank_text = st.text(min_size=1, max_size=40).filter(lambda s: s.strip() != "")

_verbs = st.sampled_from(["approve", "reject", "rollback"])
_exception_cases = st.sampled_from(_EXCEPTION_STATUS)


# --- Property -----------------------------------------------------------------


@pytest.mark.property
@settings(max_examples=150)
@given(
    verb=_verbs,
    exc_case=_exception_cases,
    actor=_nonblank_text,
    rationale=_nonblank_text,
)
def test_governance_errors_surface_as_failures_never_success(
    verb: str,
    exc_case: tuple[type[Exception], int],
    actor: str,
    rationale: str,
) -> None:
    """For any governance/publishing error on a decision, the endpoint returns a
    non-2xx failure with a reason and never a success (Req 10.13)."""
    exc_type, expected_status = exc_case
    governance = RaisingGovernance(exc_type("boom"))
    client = _seeded_client(governance)

    response = client.post(
        f"/fixes/{FIX_ID}/{verb}",
        json={"actor": actor, "rationale": rationale},
    )

    # The request reached governance (the not-found pre-check passed).
    assert len(governance.calls) == 1
    assert governance.calls[0][0] == f"{verb}_fix"

    # Never a success: always a client/server failure status.
    assert response.status_code >= 400
    assert not (200 <= response.status_code < 300)

    # The failure carries a non-empty reason.
    body = response.json()
    assert "detail" in body
    assert isinstance(body["detail"], str)
    assert body["detail"].strip() != ""

    # The status matches the exact mapping the API defines for the error type.
    assert response.status_code == expected_status
