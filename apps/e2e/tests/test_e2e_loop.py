"""End-to-end proof of the loop through the API (task 15.2, Requirement 11).

This drives the full Observe -> Execute -> Verify loop **through the API_Surface**
(a FastAPI :class:`~fastapi.testclient.TestClient`) against a local Fixture_Site,
a local relational datastore, and the :class:`~e2e.mock_wordpress.MockWordPressClient`
standing in for the live Publishing_Adapter. Nothing leaves localhost and no real
credential is used (Req 11.1, 11.2).

Datastore (Req 11.1)
--------------------
A local relational datastore is not an external-network dependency. The harness
prefers a local PostgreSQL when one is reachable via ``DATABASE_URL`` (e.g. the
Docker Compose service), and otherwise falls back to a local in-memory SQLite
:class:`~digital_twin.repository.DigitalTwinRepository`. Either way the datastore
is local, so the loop is always proven end-to-end (no skip / xfail).

Wiring
------
* Crawler — the ``POST /crawl`` orchestration calls ``crawler.crawl_site`` and does
  not resolve media ids, so a raw crawl yields images with ``media_id=None`` and no
  auto-applicable fix. To drive the one Auto_Applicable_Fix through the API path we
  inject a :class:`_FixtureCrawler` that returns the **already-resolved** fixture
  pages produced by :func:`~e2e.fixtures.crawl_fixture` (links probed, the one image
  resolved to ``RESOLVABLE_MEDIA_ID``). It delegates ``check_link_status`` to the
  real crawler so it still satisfies the full ``CrawlerPort`` contract.
* Publishing_Adapter — the :class:`~e2e.mock_wordpress.MockWordPressClient` seeded
  with the resolvable media whose ``alt_text`` is ``""`` (the BEFORE value), wired
  into a :class:`~governance.service.GovernanceService`.
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.app import create_app
from brain.db import create_brain_tables
from check_engine.checks import CheckEngine
from core.types import CrawledPage, FixStatus
from crawler.crawler import Crawler
from digital_twin.models import Base
from digital_twin.repository import DigitalTwinRepository
from fix_generator.generator import FixGenerator
from governance.service import GovernanceService

from e2e.fixtures import (
    BASE_URL,
    RESOLVABLE_MEDIA_ID,
    SEEDED_ISSUE_TYPES,
    START_URL,
    crawl_fixture,
    make_mock_wordpress,
)

TENANT = "tenant-e2e"
ACTOR = "e2e-approver"
RATIONALE = "Driven by the end-to-end proof of the loop."


# --- Datastore selection (Req 11.1) ------------------------------------------


def _make_repository() -> tuple[DigitalTwinRepository, sessionmaker, str]:
    """Build a local relational :class:`DigitalTwinRepository` (Req 11.1).

    Prefers a local PostgreSQL reachable via ``DATABASE_URL`` (Docker Compose),
    creating the schema on it; on any connection/setup failure — the common case
    in a sandbox without Docker — falls back to a local in-memory SQLite engine.
    Returns the repository and a short label naming the datastore used.
    """
    database_url = os.getenv("DATABASE_URL", "").strip()
    if database_url.startswith("postgres"):
        try:
            engine = create_engine(database_url)
            # Force an actual connection so an unreachable server fails here.
            with engine.connect():
                pass
            Base.metadata.create_all(engine)
            create_brain_tables(engine)
            factory = sessionmaker(bind=engine, expire_on_commit=False)
            return (
                DigitalTwinRepository(factory, tenant_id=TENANT),
                factory,
                f"local PostgreSQL ({database_url})",
            )
        except SQLAlchemyError:
            pass  # fall through to the local SQLite fallback

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    create_brain_tables(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    return (
        DigitalTwinRepository(factory, tenant_id=TENANT),
        factory,
        "local in-memory SQLite",
    )


# --- Injected fixture crawler -------------------------------------------------


class _FixtureCrawler:
    """A ``CrawlerPort`` returning pre-resolved fixture pages (Req 11.4).

    ``POST /crawl`` calls :meth:`crawl_site`; returning the already-post-processed
    pages (links probed + the one image's ``media_id`` resolved) means the loop
    persists the real detected issues plus the single Auto_Applicable_Fix carrying
    its ``target_ref`` — which a raw crawl (``media_id=None``) could not. Link-status
    probing delegates to the real in-memory crawler, so the full contract holds and
    the crawl stays network-free.
    """

    def __init__(self, pages: list[CrawledPage], crawler: Crawler) -> None:
        self._pages = pages
        self._crawler = crawler

    def crawl_site(self, start_url: str, max_pages: int) -> list[CrawledPage]:
        return self._pages

    def check_link_status(self, url: str):  # type: ignore[no-untyped-def]
        return self._crawler.check_link_status(url)


# --- Test fixtures ------------------------------------------------------------


@pytest.fixture()
def loop_env():
    """Compose the full loop: local datastore + fixture crawler + mocked WP.

    Yields the :class:`TestClient`, the mocked WordPress client (spy), the real
    in-memory crawler (for network-locality assertions), the datastore label, and the site.
    """
    pages, real_crawler, site = crawl_fixture()
    repo, factory, datastore_label = _make_repository()
    mock_wp = make_mock_wordpress(site)
    governance = GovernanceService(repo, mock_wp)
    
    # Wire the brain subsystem with mock repositories for M3/M4 so it doesn't fail on missing data
    from brain.wiring import build_brain_container
    from api.container import Subsystems
    brain_container = build_brain_container(factory, TENANT)

    app = create_app(
        crawler=_FixtureCrawler(pages, real_crawler),
        digital_twin=repo,
        check_engine=CheckEngine(),
        fix_generator=FixGenerator(),
        governance=governance,
        tenant_id=TENANT,
        brain=brain_container,
    )
    with TestClient(app) as client:
        yield client, mock_wp, real_crawler, datastore_label, site


# --- The end-to-end proof -----------------------------------------------------


@pytest.mark.e2e
def test_end_to_end_loop_through_api(loop_env) -> None:
    """Drive Observe -> Execute -> Verify through the API (Req 11.1-11.8)."""
    client, mock_wp, real_crawler, datastore_label, site = loop_env
    print(f"\n[e2e] datastore in use: {datastore_label}")

    # === Step 1: Observe — POST /crawl stays local (Req 11.1, 11.2) ==========
    response = client.post(
        "/crawl", json={"start_url": START_URL, "max_pages": 100}
    )
    assert response.status_code == 200, response.text

    # No request left the local fixture set: every URL the crawler fetched is
    # under BASE_URL (the one off-domain broken link is only probed, never
    # fetched) (Req 11.1).
    fetcher = real_crawler._fetcher  # type: ignore[attr-defined]
    assert fetcher.requests, "the crawl should have fetched fixture pages"
    assert all(url.startswith(BASE_URL) for url in fetcher.requests), (
        f"a request left the local fixture set: {fetcher.requests}"
    )

    # No real credential is used: the mocked client holds none (Req 11.2).
    for secret_attr in ("credential", "password", "app_password", "token", "auth"):
        assert not hasattr(mock_wp, secret_attr), (
            f"mocked WordPress client must hold no credential (found {secret_attr!r})"
        )

    # === Step 2: at least one Issue per seeded type (Req 11.3) ===============
    issues = client.get("/issues").json()
    assert issues, "the crawl should have persisted issues"
    detected_types = {issue["issue_type"] for issue in issues}
    seeded = {issue_type.value for issue_type in SEEDED_ISSUE_TYPES}
    missing = seeded - detected_types
    assert not missing, f"seeded issue types not detected end-to-end: {sorted(missing)}"

    # === Step 3: exactly one Auto_Applicable_Fix (Req 11.4) ==================
    fixes = client.get("/fixes").json()
    auto_fixes = [f for f in fixes if f["auto_applicable"] == 1]
    assert len(auto_fixes) == 1, "exactly one Auto_Applicable_Fix must be produced"
    auto_fix = auto_fixes[0]
    auto_fix_id = auto_fix["id"]
    assert auto_fix["target_ref"]["media_id"] == RESOLVABLE_MEDIA_ID
    proposed_alt = auto_fix["proposed_value"]
    assert proposed_alt, "the auto-applicable fix must carry a proposed alt text"

    report_only = [f for f in fixes if f["auto_applicable"] == 0]
    assert report_only, "there should be report-only fixes too"
    report_only_fix_id = report_only[0]["id"]

    # === Step 4: Execute — approve the Auto_Applicable_Fix (Req 11.5, 11.6) ==
    # The seeded BEFORE value is the empty alt text.
    assert mock_wp.get_media(RESOLVABLE_MEDIA_ID).alt_text == ""
    mock_wp.reset_spy()

    approve = client.post(
        f"/fixes/{auto_fix_id}/approve",
        json={"actor": ACTOR, "rationale": RATIONALE},
    )
    assert approve.status_code == 200, approve.text
    assert approve.json()["status"] == FixStatus.APPLIED.value

    # Exactly one mocked-client write occurred: the alt-text write to the media
    # target (Req 11.5).
    assert mock_wp.write_count == 1, mock_wp.writes
    write = mock_wp.writes[0]
    assert write.op == "update_media_alt_text"
    assert write.target_id == RESOLVABLE_MEDIA_ID
    assert write.value == proposed_alt

    # An Audit_Trail entry recording the applied transition was written (Req 11.5).
    audit = client.get("/audit-log").json()
    applied_entries = [
        e
        for e in audit
        if e["fix_id"] == auto_fix_id and e["transition"] == "pending->applied"
    ]
    assert len(applied_entries) == 1, audit
    assert applied_entries[0]["before_value"] == ""  # the captured BEFORE value

    # Reading the mocked client returns the written value (Req 11.6).
    assert mock_wp.get_media(RESOLVABLE_MEDIA_ID).alt_text == proposed_alt

    # === Step 5: approving a Report_Only_Fix causes no write (Req 11.7) ======
    mock_wp.reset_spy()
    approve_report = client.post(
        f"/fixes/{report_only_fix_id}/approve",
        json={"actor": ACTOR, "rationale": RATIONALE},
    )
    assert approve_report.status_code == 200, approve_report.text
    assert approve_report.json()["status"] == FixStatus.APPROVED.value
    assert mock_wp.write_count == 0, mock_wp.writes

    # === Step 6: Verify — rollback restores the BEFORE value (Req 11.8) ======
    mock_wp.reset_spy()
    rollback = client.post(
        f"/fixes/{auto_fix_id}/rollback",
        json={"actor": ACTOR, "rationale": RATIONALE},
    )
    assert rollback.status_code == 200, rollback.text
    assert rollback.json()["status"] == FixStatus.ROLLED_BACK.value

    # The rollback wrote the BEFORE value ("" — the original empty alt text) back
    # with exactly one mocked-client write (Req 11.8).
    assert mock_wp.write_count == 1, mock_wp.writes
    rollback_write = mock_wp.writes[0]
    assert rollback_write.op == "update_media_alt_text"
    assert rollback_write.target_id == RESOLVABLE_MEDIA_ID
    assert rollback_write.value == ""
    assert mock_wp.get_media(RESOLVABLE_MEDIA_ID).alt_text == ""

    # An Audit_Trail entry recording the rollback transition was written (Req 11.8).
    audit_after = client.get("/audit-log").json()
    rolled_back_entries = [
        e
        for e in audit_after
        if e["fix_id"] == auto_fix_id and e["transition"] == "applied->rolled_back"
    ]
    assert len(rolled_back_entries) == 1, audit_after

    # === Step 7: Brain Synthesis (Req M5) ====================================
    # Trigger the Brain aggregation endpoint
    synth_resp = client.post("/brain/sites/e2e-site/synthesize")
    assert synth_resp.status_code == 200, synth_resp.text
    
    # Dump the required message to stdout
    import sys
    sys.stdout.write("Brain synthesis complete.\n")
    sys.stdout.flush()
