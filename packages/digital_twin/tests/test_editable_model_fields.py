"""Milestone 4 — Digital Twin editable-model persistence.

Verifies that the crawl-derived editable-model fields round-trip through the
repository, that the internal link graph resolves destination page ids from real
data, and that the URL -> WordPress page/post identity mapping populates from a
live listing. Uses in-memory SQLite (hermetic; no external services).
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from core.types import CrawledPage, HeadingRef, LinkStatus
from digital_twin.models import Base, Link as LinkRow, Page as PageRow
from digital_twin.repository import DigitalTwinRepository


@pytest.fixture()
def repo():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    return DigitalTwinRepository(factory, tenant_id="t1"), factory


def _pages(now):
    home = CrawledPage(
        url="https://x.com/", final_url="https://x.com/", status_code=200,
        title="Home", crawled_at=now, canonical_url="https://x.com/",
        headings=[HeadingRef(level=1, text="Welcome")],
        schema_types=["Organization"],
        links=[
            LinkStatus(url="https://x.com/services", reachable=True, status_code=200,
                       anchor_text="Our Services", is_internal=True),
            LinkStatus(url="https://external.com/x", reachable=True, status_code=200,
                       anchor_text="ext", is_internal=False),
        ],
    )
    services = CrawledPage(
        url="https://x.com/services", final_url="https://x.com/services",
        status_code=200, title="Services", crawled_at=now, slug="services",
        headings=[HeadingRef(level=1, text="Services"), HeadingRef(level=2, text="SEO")],
        schema_types=["Service"], links=[],
    )
    return home, services


def test_editable_fields_round_trip(repo):
    r, _ = repo
    now = datetime.now(timezone.utc)
    r.upsert_pages("t1", list(_pages(now)))

    pages = {p.url: p for p in r.list_pages("t1")}
    home = pages["https://x.com/"]
    assert home.canonical_url == "https://x.com/"
    assert home.schema_types == ["Organization"]
    assert home.headings[0].text == "Welcome"
    internal = [link for link in home.links if link.is_internal]
    assert len(internal) == 1 and internal[0].anchor_text == "Our Services"

    services = pages["https://x.com/services"]
    assert services.slug == "services"
    assert [h.level for h in services.headings] == [1, 2]


def test_internal_link_graph_resolves_destination_page_id(repo):
    r, factory = repo
    now = datetime.now(timezone.utc)
    r.upsert_pages("t1", list(_pages(now)))

    with factory() as session:
        services_id = session.execute(
            select(PageRow.id).where(PageRow.url == "https://x.com/services")
        ).scalar_one()
        internal_edge = session.execute(
            select(LinkRow).where(LinkRow.href == "https://x.com/services")
        ).scalar_one()
        assert internal_edge.to_page_id == services_id
        assert internal_edge.is_internal is True

        external_edge = session.execute(
            select(LinkRow).where(LinkRow.href == "https://external.com/x")
        ).scalar_one()
        assert external_edge.to_page_id is None


def test_resolve_wp_identities_maps_by_url(repo):
    r, factory = repo
    now = datetime.now(timezone.utc)
    r.upsert_pages("t1", list(_pages(now)))

    mapped = r.resolve_wp_identities(
        "t1",
        [("https://x.com/services", 42, "page"), ("https://x.com/", 7, "page")],
    )
    assert mapped == 2

    with factory() as session:
        row = session.execute(
            select(PageRow).where(PageRow.url == "https://x.com/services")
        ).scalar_one()
        assert row.wp_page_id == 42 and row.wp_post_type == "page"


def test_resolve_wp_identities_skips_unmatched(repo):
    r, _ = repo
    now = datetime.now(timezone.utc)
    r.upsert_pages("t1", list(_pages(now)))
    # A WP entry whose link matches no crawled page must not fabricate a mapping.
    assert r.resolve_wp_identities("t1", [("https://x.com/ghost", 99, "page")]) == 0
