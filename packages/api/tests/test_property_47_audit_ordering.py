"""Property 47 — Audit log is ordered most-recent first.

Feature: website-orchestrator-milestone-0, Property 47: Audit log is ordered
most-recent first.

**Validates: Requirements 10.7**

``GET /audit-log`` exposes the Audit_Trail (Req 10.7). Regardless of the order in
which :meth:`DigitalTwinRepository.append_audit_entry` is called, the endpoint
must return the entries ordered **most-recent first** — i.e. by descending
``created_at`` (with a ``id`` descending tiebreak in the repository).

This property drives that guarantee network-free: the FastAPI
:class:`~fastapi.testclient.TestClient` is wired to a real
:class:`~digital_twin.repository.DigitalTwinRepository` backed by in-memory
SQLite. For each example a *fresh* repo is seeded with ``N`` ``AuditEntry``
records that have **distinct** ``created_at`` timestamps (keeping them distinct
avoids tie ambiguity), appended in an arbitrary (shuffled) insertion order with
arbitrary-but-valid non-empty ``actor`` / ``rationale`` / ``fix_id`` /
``transition``. Then ``GET /audit-log`` is issued and we assert:

* the returned ``created_at`` values are in non-increasing (descending) order,
* the set of returned ``id`` values equals the set that was appended (nothing
  lost or invented),
* the first returned entry is the newest (max ``created_at``).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

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
from governance.service import GovernanceService

from core.types import AuditEntry

from api import create_app

TENANT = "tenant-a"

_BASE = datetime(2024, 1, 1, tzinfo=timezone.utc)


# --- Fakes --------------------------------------------------------------------


class FakeCrawler:
    """A CrawlerPort fake; never invoked by the audit-log read endpoint."""

    def crawl_site(self, start_url: str, max_pages: int):  # pragma: no cover
        raise NotImplementedError

    def check_link_status(self, url: str):  # pragma: no cover
        raise NotImplementedError


class FakePublishingAdapter:
    """Minimal PublishingAdapterPort so the Governance_Layer can be built."""

    def list_pages(self):  # pragma: no cover - unused
        return []

    def get_page(self, page_id: int):  # pragma: no cover - unused
        raise NotImplementedError

    def update_page_content(self, page_id: int, content: str):  # pragma: no cover
        raise NotImplementedError

    def get_media(self, media_id: int):  # pragma: no cover - unused
        raise NotImplementedError

    def update_media_alt_text(self, media_id: int, alt_text: str):  # pragma: no cover
        raise NotImplementedError


# --- App builder --------------------------------------------------------------


def _build_app():
    """Build an app wired to a fresh in-memory repo, returning ``(app, repo)``."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    repo = DigitalTwinRepository(session_factory, tenant_id=TENANT)
    governance = GovernanceService(repo, FakePublishingAdapter())

    app = create_app(
        crawler=FakeCrawler(),
        digital_twin=repo,
        check_engine=CheckEngine(),
        fix_generator=FixGenerator(),
        governance=governance,
        tenant_id=TENANT,
    )
    return app, repo


# --- Strategies ---------------------------------------------------------------

# Non-empty text for the arbitrary-but-valid string fields.
_nonempty_text = st.text(min_size=1, max_size=20).filter(lambda s: s.strip() != "")


@st.composite
def _audit_entries(draw: st.DrawFn) -> list[AuditEntry]:
    """Generate a list of ``AuditEntry`` with *distinct* ``created_at`` values,
    to be appended in an arbitrary (shuffled) insertion order.

    Distinct timestamps are produced from a set of unique minute offsets from a
    fixed UTC base, avoiding tie ambiguity so the expected ordering is total.
    """
    # Distinct offsets -> distinct created_at values; 1..12 entries per example.
    offsets = draw(
        st.lists(
            st.integers(min_value=0, max_value=100_000),
            min_size=1,
            max_size=12,
            unique=True,
        )
    )
    n = len(offsets)
    actors = draw(st.lists(_nonempty_text, min_size=n, max_size=n))
    rationales = draw(st.lists(_nonempty_text, min_size=n, max_size=n))
    transitions = draw(
        st.lists(
            st.sampled_from(
                [
                    "pending->approved",
                    "pending->rejected",
                    "approved->applied",
                    "applied->rolled_back",
                ]
            ),
            min_size=n,
            max_size=n,
        )
    )

    entries = [
        AuditEntry(
            id=f"audit-{i}",
            tenant_id=TENANT,
            fix_id=f"fix-{i}",
            actor=actors[i],
            rationale=rationales[i],
            transition=transitions[i],
            created_at=_BASE + timedelta(minutes=offset),
        )
        for i, offset in enumerate(offsets)
    ]

    # Append in an arbitrary order that is independent of chronological order.
    return draw(st.permutations(entries))


# --- Property 47 --------------------------------------------------------------


@settings(max_examples=150)
@given(entries=_audit_entries())
def test_property_47_audit_log_ordered_most_recent_first(
    entries: list[AuditEntry],
) -> None:
    """For any set of audit entries appended in arbitrary order, ``GET
    /audit-log`` returns them ordered most-recent first (Req 10.7)."""
    app, repo = _build_app()
    for entry in entries:
        repo.append_audit_entry(TENANT, entry)

    client = TestClient(app)
    response = client.get("/audit-log")

    assert response.status_code == 200
    body = response.json()

    # Nothing lost or invented: the returned ids match exactly what we appended.
    assert {e["id"] for e in body} == {e.id for e in entries}

    returned_times = [
        datetime.fromisoformat(e["created_at"].replace("Z", "+00:00")) for e in body
    ]

    # created_at values are in non-increasing (descending) order.
    assert all(
        earlier >= later
        for earlier, later in zip(returned_times, returned_times[1:])
    )

    # The first returned entry is the newest.
    assert returned_times[0] == max(e.created_at for e in entries)
