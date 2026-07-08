"""Property 49 — Unknown fix ids on decision endpoints return not-found
without invoking Governance.

Feature: website-orchestrator-milestone-0, Property 49: Unknown fix ids on
decision endpoints return not-found without invoking Governance.

**Validates: Requirements 10.12**

Req 10.12: IF an approve, reject, or rollback request references an unknown
SuggestedFix, THEN THE API_Surface SHALL return a response indicating the fix
was not found and SHALL NOT invoke the Governance_Layer.

The three decision endpoints — ``POST /fixes/{id}/approve|reject|rollback`` —
each call ``digital_twin.get_fix`` *before* delegating to the Governance_Layer.
When the fix id is unknown that pre-check returns ``None`` and the handler
returns a ``404`` not-found response without ever touching Governance.

This property drives that guarantee network-free: the FastAPI
:class:`~fastapi.testclient.TestClient` is wired to a real
:class:`~digital_twin.repository.DigitalTwinRepository` backed by in-memory
SQLite, the real Check_Engine/Fix_Generator, a **spy** Governance_Layer, and a
minimal fake Crawler. The :class:`SpyGovernance` records every call and raises
an ``AssertionError`` if any decision method is reached, so any invocation for
an unknown id fails loudly.

For every generated (verb, unknown id, actor, rationale) tuple we seed the repo
either empty or with fixes whose ids all differ from the target, then assert the
response is ``404`` and that Governance was never invoked (``spy.calls == []``).
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

from core.types import FixStatus, FixType, SuggestedFix

from api import create_app

TENANT = "tenant-a"

DECISION_VERBS = ("approve", "reject", "rollback")


# --- Fakes --------------------------------------------------------------------


class FakeCrawler:
    """A CrawlerPort fake; never invoked by the decision endpoints."""

    def crawl_site(self, start_url: str, max_pages: int):  # pragma: no cover
        raise NotImplementedError

    def check_link_status(self, url: str):  # pragma: no cover
        raise NotImplementedError


class SpyGovernance:
    """A GovernancePort spy that records calls and refuses to be invoked.

    Every decision method appends to ``calls`` and immediately raises an
    ``AssertionError``: reaching any of them for an unknown fix id would violate
    Req 10.12. ``list_pending_fixes`` is not part of the decision path and is
    harmless, but the decision endpoints never call it either.
    """

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


# --- App builder --------------------------------------------------------------


def _build_app(governance):
    """Build a fresh app wired to a real in-memory repo and the given governance.

    A fresh in-memory SQLite DB per call gives each example a clean persistence
    slate. ``StaticPool`` + ``check_same_thread=False`` keeps a single
    connection so tables created here are visible to the handler thread the
    TestClient runs in.
    """
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    repo = DigitalTwinRepository(session_factory, tenant_id=TENANT)

    app = create_app(
        crawler=FakeCrawler(),
        digital_twin=repo,
        check_engine=CheckEngine(),
        fix_generator=FixGenerator(),
        governance=governance,
        tenant_id=TENANT,
    )
    return app, repo


def _pending_fix(fix_id: str) -> SuggestedFix:
    """A persisted pending Report_Only_Fix used only to populate the repo with
    ids that differ from the (unknown) target id."""
    return SuggestedFix(
        id=fix_id,
        tenant_id=TENANT,
        issue_id=f"issue-for-{fix_id}",
        fix_type=FixType.UPDATE_PAGE_CONTENT,
        auto_applicable=0,
        reason="Report only",
        status=FixStatus.PENDING,
    )


# --- Generators ---------------------------------------------------------------

#: Path-safe, non-empty fix-id tokens (URL path segment, no slashes/spaces).
_ID_TOKENS = st.text(
    alphabet=st.characters(
        whitelist_categories=("Lu", "Ll", "Nd"),
        whitelist_characters="-_",
    ),
    min_size=1,
    max_size=24,
).filter(lambda s: s.strip() == s and "/" not in s and s != "")

#: A decision verb.
_VERBS = st.sampled_from(DECISION_VERBS)

#: Valid decision body: non-blank actor and non-blank rationale.
_NONBLANK_TEXT = st.text(min_size=1, max_size=40).filter(lambda s: s.strip() != "")


@st.composite
def _unknown_id_cases(draw) -> dict:
    """Draw a target id and a set of *seed* ids all distinct from the target.

    Half the time the repo is left empty; otherwise it is seeded with fixes
    whose ids are guaranteed different from the target, so the target id is
    always unknown regardless of seeding.
    """
    target = draw(_ID_TOKENS)
    seed_ids = draw(
        st.lists(_ID_TOKENS, min_size=0, max_size=4, unique=True).map(
            lambda ids: [i for i in ids if i != target]
        )
    )
    verb = draw(_VERBS)
    actor = draw(_NONBLANK_TEXT)
    rationale = draw(_NONBLANK_TEXT)
    return {
        "target": target,
        "seed_ids": seed_ids,
        "verb": verb,
        "actor": actor,
        "rationale": rationale,
    }


# --- Property 49 --------------------------------------------------------------


@pytest.mark.property
@settings(max_examples=200, deadline=None)
@given(case=_unknown_id_cases())
def test_property_49_unknown_id_decisions_return_404_without_governance(
    case: dict,
) -> None:
    """Any decision verb on an unknown fix id returns 404 and never invokes
    the Governance_Layer.

    **Validates: Requirements 10.12**
    """
    spy = SpyGovernance()
    app, repo = _build_app(spy)

    # Seed the repo with fixes whose ids all differ from the target, so the
    # target id is genuinely unknown (the empty-seed case is covered too).
    if case["seed_ids"]:
        repo.persist_fixes(TENANT, [_pending_fix(i) for i in case["seed_ids"]])

    # Sanity: the target id must not be persisted.
    assert repo.get_fix(TENANT, case["target"]) is None

    client = TestClient(app)
    response = client.post(
        f"/fixes/{case['target']}/{case['verb']}",
        json={"actor": case["actor"], "rationale": case["rationale"]},
    )

    # Not-found response (Req 10.12).
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()

    # The Governance_Layer was never invoked for the unknown-id decision.
    assert spy.calls == []
