"""SaaS Database module — SQLAlchemy ORM base and helper utilities."""

from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import DateTime, Engine, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

__all__ = [
    "SaaSBase",
    "create_saas_tables",
]


class SaaSBase(DeclarativeBase):
    """Declarative base for all SaaS platform database models."""


def create_saas_tables(engine: Engine) -> None:
    """Create all SaaS tables in the target database engine."""
    SaaSBase.metadata.create_all(engine)
