"""Shared test fixtures for the onboarding package.

Provides an in-memory SQLite-backed OnboardingRepository and the reusable
subsystem fakes so every test is network-free and deterministic.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.types import CrawledPage, ImageRef, LinkStatus

from onboarding.models import Base
from onboarding.repository import OnboardingRepository


TENANT = "tenant-test"


@pytest.fixture
def session_factory():
    """An in-memory SQLite session factory shared per test."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture
def repo(session_factory):
    """A tenant-scoped OnboardingRepository over in-memory SQLite."""
    return OnboardingRepository(session_factory, tenant_id=TENANT)


@pytest.fixture
def fake_crawled_pages():
    """Two canned crawled pages for crawl/twin tests."""
    now = datetime(2024, 1, 1, tzinfo=timezone.utc)
    home = CrawledPage(
        url="https://example.com/",
        final_url="https://example.com/",
        status_code=200,
        title="Home",
        meta_description="Welcome",
        word_count=500,
        has_schema=True,
        images=[ImageRef(media_id=1, filename="hero.jpg", alt_text=None)],
        links=[LinkStatus(url="https://example.com/about", status_code=200, reachable=True)],
        crawled_at=now,
    )
    about = CrawledPage(
        url="https://example.com/about",
        final_url="https://example.com/about",
        status_code=200,
        title="About",
        meta_description=None,
        word_count=50,
        has_schema=False,
        images=[],
        links=[],
        crawled_at=now,
    )
    return [home, about]
