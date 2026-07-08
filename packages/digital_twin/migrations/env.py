"""Alembic environment for the Digital_Twin schema.

Wires Alembic to:
- the Core_Package-sourced ``DATABASE_URL`` (via :func:`digital_twin.db.get_database_url`,
  Req 14.1), rather than a hardcoded URL in ``alembic.ini``; and
- the Digital_Twin ORM metadata (:data:`digital_twin.models.Base.metadata`), so
  ``--autogenerate`` and ``upgrade`` operate on the six relational tables
  (``pages``, ``links``, ``page_metadata``, ``issues``, ``suggested_fixes``,
  ``audit_trail``).
"""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from digital_twin.db import get_database_url
from digital_twin.models import Base

# Alembic Config object providing access to values within alembic.ini.
config = context.config

# Resolve the datastore URL from Core_Package configuration (Req 14.1).
config.set_main_option("sqlalchemy.url", get_database_url())

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata for 'autogenerate' support.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (emit SQL without a DBAPI connection)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode against a live connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
