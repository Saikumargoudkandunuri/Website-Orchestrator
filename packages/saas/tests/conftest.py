"""Test fixtures configuration for SaaS Package."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from saas.db import SaaSBase, create_saas_tables
from brain.db import BrainBase
from enterprise_intelligence.db import create_enterprise_intelligence_tables


@pytest.fixture
def db_session_factory():
    """Create in-memory SQLite database session factory for testing."""
    engine = create_engine("sqlite:///:memory:")
    # Create all schemas
    BrainBase.metadata.create_all(engine)
    create_enterprise_intelligence_tables(engine)
    create_saas_tables(engine)
    return sessionmaker(bind=engine)
