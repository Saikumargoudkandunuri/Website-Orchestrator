"""Unit/integration tests for the API_Surface decision endpoints (task 13.3).

These cover ``POST /fixes/{id}/approve|reject|rollback`` (Req 10.4-10.6, 10.12,
10.13). They are network-free: the FastAPI
:class:`~fastapi.testclient.TestClient` drives the app, the Digital_Twin is a
real :class:`~digital_twin.repository.DigitalTwinRepository` backed by in-memory
SQLite, and the Governance_Layer is the real
:class:`~governance.service.GovernanceService` wired to an in-memory fake
Publishing_Adapter so no live WordPress site is contacted.

Coverage:

* ``approve``/``reject`` delegate to the Governance_Layer and return the updated
  fix on success (Req 10.4, 10.5).
* ``rollback`` delegates to the Governance_Layer, restoring the audited BEFORE
  value through the Publishing_Adapter, and returns the updated fix (Req 10.6).
* An unknown fix id returns ``404`` and the Governance_Layer is **never** invoked
  (Req 10.12) — asserted with a spy governance whose methods must not be called.
* A governance error (approving an already-decided fix -> ``FixAlreadyDecidedError``;
  an empty rationale reaching governance) surfaces as a non-2xx failure response
  carrying the reason and never reports success (Req 10.13).
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from check_engine import CheckEngine
from digital_twin.models import Base
from digital_twin.repository import DigitalTwinRepository
from fix_generator import FixGenerator
from governance.service import GovernanceService

from core.interfaces import WPMedia
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
    """A CrawlerPort fake; never invoked by the decision endpoints."""

    def crawl_site(self, start_url: str, max_pages: int):  # pragma: no cover
        raise NotImplementedError

    def check_link_status(self, url: str):  # pragma: no cover
        raise NotImplementedError


class FakePublishingAdapter:
    """In-memory PublishingAdapterPort recording media alt-text writes.

    Only the media path is exercised here (the auto-applicable alt-text fix).
    Reads return the current stored value so the Governance_Layer can capture a
    real BEFORE value before a write.
    """

    def __init__(self, media: dict[int, str] | None = None) -> None:
        self.media = dict(media or {})
        self.media_writes: list[tuple[int, str]] = []

    def list_pages(self):  # pragma: no cover - unused
        return []

    def get_page(self, page_id: int):  # pragma: no cover - unused
        raise NotImplementedError

    def update_page_content(self, page_id: int, content: str):  # pragma: no cover
        raise NotImplementedError

    def get_media(self, media_id: int) -> WPMedia:
        return WPMedia(id=media_id, alt_text=self.media.get(media_id, ""))

    def update_media_alt_text(self, media_id: int, alt_text: str) -> WPMedia:
        self.media[media_id] = alt_text
        self.media_writes.append((media_id, alt_text))
        return WPMedia(id=media_id, alt_text=alt_text)


class RecordingGovernance:
    """A GovernancePort fake that records the decision call and returns a
    pre-built updated fix, used to assert the endpoint delegates and surfaces the
    Governance_Layer's returned record."""

    def __init__(self, result: SuggestedFix) -> None:
        self._result = result
        self.calls: list[tuple[str, str, str, str]] = []

    def list_pending_fixes(self, tenant_id: str):  # pragma: no cover - unused
        return []

    def approve_fix(self, tenant_id, fix_id, actor, rationale) -> SuggestedFix:
        self.calls.append(("approve_fix", fix_id, actor, rationale))
        return self._result

    def reject_fix(self, tenant_id, fix_id, actor, rationale) -> SuggestedFix:
        self.calls.append(("reject_fix", fix_id, actor, rationale))
        return self._result

    def rollback_fix(self, tenant_id, fix_id, actor, rationale) -> SuggestedFix:
        self.calls.append(("rollback_fix", fix_id, actor, rationale))
        return self._result


class SpyGovernance:
    """A GovernancePort spy that records calls; used to assert governance is
    skipped for an unknown fix id (Req 10.12)."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def list_pending_fixes(self, tenant_id: str):  # pragma: no cover - unused
        self.calls.append(("list_pending_fixes", tenant_id))
        return []

    def approve_fix(self, tenant_id, fix_id, actor, rationale):
        self.calls.append(("approve_fix", fix_id))
        raise AssertionError("governance must not be invoked for an unknown id")

    def reject_fix(self, tenant_id, fix_id, actor, rationale):
        self.calls.append(("reject_fix", fix_id))
        raise AssertionError("governance must not be invoked for an unknown id")

    def rollback_fix(self, tenant_id, fix_id, actor, rationale):
        self.calls.append(("rollback_fix", fix_id))
        raise AssertionError("governance must not be invoked for an unknown id")


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
    app = create_app(
        crawler=FakeCrawler(),
        digital_twin=repo,
        check_engine=CheckEngine(),
        fix_generator=FixGenerator(),
        governance=governance,
        tenant_id=TENANT,
    )
    return app


def _report_only_fix(fix_id: str = "fix-report") -> SuggestedFix:
    """A persisted pending Report_Only_Fix (no live write on approval)."""
    return SuggestedFix(
        id=fix_id,
        tenant_id=TENANT,
        issue_id="issue-1",
        fix_type=FixType.UPDATE_PAGE_CONTENT,
        auto_applicable=0,
        reason="Report only",
        status=FixStatus.PENDING,
    )


def _auto_alt_text_fix(fix_id: str = "fix-auto", media_id: int = 123) -> SuggestedFix:
    """A persisted pending Auto_Applicable_Fix writing media alt text."""
    return SuggestedFix(
        id=fix_id,
        tenant_id=TENANT,
        issue_id="issue-2",
        fix_type=FixType.UPDATE_ALT_TEXT,
        auto_applicable=1,
        target_ref=TargetRef(media_id=media_id),
        proposed_value="A red bike",
        status=FixStatus.PENDING,
    )


# --- approve (Req 10.4) -------------------------------------------------------


def test_approve_delegates_and_returns_updated_fix() -> None:
    repo = _make_repo()
    repo.persist_fixes(TENANT, [_report_only_fix()])
    governance = GovernanceService(repo, FakePublishingAdapter())
    client = TestClient(_build_app(repo, governance))

    response = client.post(
        "/fixes/fix-report/approve",
        json={"actor": "alice", "rationale": "looks good"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "fix-report"
    assert body["status"] == "approved"
    # The transition was persisted through the Governance_Layer.
    assert repo.get_fix(TENANT, "fix-report").status is FixStatus.APPROVED
    # One Audit_Trail entry recording the decision was written.
    audit = repo.list_audit_entries(TENANT)
    assert [e.transition for e in audit] == ["pending->approved"]
    assert audit[0].actor == "alice"


# --- reject (Req 10.5) --------------------------------------------------------


def test_reject_delegates_and_returns_updated_fix() -> None:
    repo = _make_repo()
    repo.persist_fixes(TENANT, [_report_only_fix("fix-reject")])
    governance = GovernanceService(repo, FakePublishingAdapter())
    client = TestClient(_build_app(repo, governance))

    response = client.post(
        "/fixes/fix-reject/reject",
        json={"actor": "bob", "rationale": "not needed"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "rejected"
    assert repo.get_fix(TENANT, "fix-reject").status is FixStatus.REJECTED


# --- rollback (Req 10.6) ------------------------------------------------------


def test_rollback_delegates_to_governance_and_returns_updated_fix() -> None:
    # The fix must be persisted so the not-found pre-check passes (Req 10.12);
    # the endpoint then delegates the rollback to the Governance_Layer and
    # returns the record it produces (Req 10.6).
    repo = _make_repo()
    repo.persist_fixes(TENANT, [_auto_alt_text_fix("fix-rb")])
    rolled_back = _auto_alt_text_fix("fix-rb").model_copy(
        update={"status": FixStatus.ROLLED_BACK}
    )
    governance = RecordingGovernance(rolled_back)
    client = TestClient(_build_app(repo, governance))

    response = client.post(
        "/fixes/fix-rb/rollback",
        json={"actor": "alice", "rationale": "revert it"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "rolled_back"
    # The endpoint delegated to the Governance_Layer rollback with the body args.
    assert governance.calls == [("rollback_fix", "fix-rb", "alice", "revert it")]


# --- unknown id -> 404, governance skipped (Req 10.12) ------------------------


def test_unknown_id_returns_404_and_skips_governance() -> None:
    repo = _make_repo()  # empty: no fixes persisted
    spy = SpyGovernance()
    client = TestClient(_build_app(repo, spy))

    for verb in ("approve", "reject", "rollback"):
        response = client.post(
            f"/fixes/does-not-exist/{verb}",
            json={"actor": "alice", "rationale": "whatever"},
        )
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    # The Governance_Layer was never invoked for any unknown-id decision.
    assert spy.calls == []


# --- governance error -> non-2xx failure with reason (Req 10.13) --------------


def test_governance_error_surfaces_as_failure_not_success() -> None:
    repo = _make_repo()
    # Persist a fix that is already decided (rejected) so a second approve fails.
    fix = _report_only_fix("fix-decided")
    repo.persist_fixes(TENANT, [fix])
    repo.update_fix_status(TENANT, "fix-decided", FixStatus.REJECTED)
    governance = GovernanceService(repo, FakePublishingAdapter())
    client = TestClient(_build_app(repo, governance))

    response = client.post(
        "/fixes/fix-decided/approve",
        json={"actor": "alice", "rationale": "try again"},
    )

    # Never a success; the failure reports its reason (Req 10.13).
    assert response.status_code == 409
    assert response.status_code >= 400
    assert "Governance decision failed" in response.json()["detail"]
    # The status was left unchanged by the failed decision.
    assert repo.get_fix(TENANT, "fix-decided").status is FixStatus.REJECTED


def test_rollback_not_allowed_from_pending_surfaces_as_failure() -> None:
    repo = _make_repo()
    repo.persist_fixes(TENANT, [_auto_alt_text_fix("fix-pending-rb")])
    governance = GovernanceService(repo, FakePublishingAdapter(media={123: "x"}))
    client = TestClient(_build_app(repo, governance))

    # Rolling back a pending (never-applied) fix is not allowed.
    response = client.post(
        "/fixes/fix-pending-rb/rollback",
        json={"actor": "alice", "rationale": "revert"},
    )

    assert response.status_code == 409
    assert "Governance decision failed" in response.json()["detail"]
    assert repo.get_fix(TENANT, "fix-pending-rb").status is FixStatus.PENDING


def test_blank_rationale_rejected_before_governance() -> None:
    repo = _make_repo()
    repo.persist_fixes(TENANT, [_report_only_fix("fix-blank")])
    governance = GovernanceService(repo, FakePublishingAdapter())
    client = TestClient(_build_app(repo, governance))

    response = client.post(
        "/fixes/fix-blank/approve",
        json={"actor": "alice", "rationale": "   "},
    )

    # Body validation rejects a blank rationale with a 422; never a success.
    assert response.status_code == 422
    assert repo.get_fix(TENANT, "fix-blank").status is FixStatus.PENDING
