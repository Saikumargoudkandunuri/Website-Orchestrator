"""Shared fixtures for the intelligence test suite.

All tests are network-free: the fake AI provider is used exclusively (§9), and
persistence is in-memory SQLite.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.types import CrawledPage, ImageRef, LinkStatus
from intelligence.ai.providers.fake_provider import FakeProvider
from intelligence.api.wiring import build_intelligence_container
from intelligence.identifiers import page_id_for
from intelligence.repositories import create_intelligence_tables

TENANT = "tenant-test"
NOW = datetime(2024, 1, 1, tzinfo=timezone.utc)

_SAMPLE_HTML = """<html><head>
<title>Modular Kitchens Hyderabad</title>
<meta name="description" content="Custom kitchens">
</head><body>
<h1>Modular Kitchens in Hyderabad</h1>
<p>We design modular kitchens for Hyderabad homes with expert installation and
ongoing service for modern families across the whole city and its suburbs.</p>
<p>Our process covers on-site measurement, 3D design, manufacturing, and
professional installation handled end to end by our own trained team.</p>
<img src="/img/red-bike.jpg">
<img src="/img/team.jpg" alt="The team">
</body></html>"""


@pytest.fixture()
def sample_page() -> CrawledPage:
    return CrawledPage(
        url="https://example.com/kitchens",
        final_url="https://example.com/kitchens",
        status_code=200,
        title="Modular Kitchens Hyderabad",
        meta_description=None,
        word_count=45,
        html=_SAMPLE_HTML,
        images=[
            ImageRef(media_id=None, filename="red-bike.jpg", alt_text=None),
            ImageRef(media_id=None, filename="team.jpg", alt_text="The team"),
        ],
        links=[
            LinkStatus(url="https://example.com/about", status_code=200, reachable=True),
            LinkStatus(url="https://example.com/dead", status_code=404, reachable=False),
        ],
        has_schema=False,
        crawled_at=NOW,
    )


@pytest.fixture()
def session_factory():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    create_intelligence_tables(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture()
def container(session_factory):
    return build_intelligence_container(session_factory, TENANT, provider=FakeProvider())


@pytest.fixture()
def page_id(sample_page) -> str:
    return page_id_for(TENANT, sample_page.url)
