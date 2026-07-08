"""Digital_Twin database wiring — engine, sessions, and the DATABASE_URL source.

The canonical source of ``DATABASE_URL`` is the Core_Package configuration
(:mod:`core.config`), which loads settings from the environment or a ``.env``
file at startup (Req 14.1). Alembic and the repository layer obtain the URL
through :func:`get_database_url` so there is a single place that knows how to
resolve it.

Running database migrations should not require the WordPress
``Application_Password`` secret to be configured, so if the full Core_Package
``Settings`` cannot be constructed (e.g. the secret is absent in a
migration-only environment) we fall back to reading ``DATABASE_URL`` directly
from the environment / ``.env``. This keeps the datastore URL sourced from the
same configuration surface without coupling migrations to unrelated secrets.
"""

from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

__all__ = ["get_database_url", "create_db_engine", "make_session_factory"]


def _read_database_url_from_env() -> str | None:
    """Return ``DATABASE_URL`` from the process env or a nearby ``.env`` file."""
    value = os.getenv("DATABASE_URL")
    if value:
        return value

    # Best-effort .env lookup so `alembic` invoked from the repo root still finds
    # the configured URL. Walk up from CWD looking for a .env file.
    cwd = Path.cwd()
    for directory in (cwd, *cwd.parents):
        env_file = directory / ".env"
        if env_file.is_file():
            for raw in env_file.read_text(encoding="utf-8").splitlines():
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                if key.strip() == "DATABASE_URL":
                    return val.strip().strip('"').strip("'")
            break
    return None


def get_database_url() -> str:
    """Resolve the datastore URL, preferring validated Core_Package settings.

    Tries :func:`core.config.get_settings` first (Req 14.1). If that cannot be
    constructed (for example the WordPress secret is not configured in a
    migration-only context), falls back to reading ``DATABASE_URL`` directly
    from the environment or a ``.env`` file.
    """
    try:
        from core.config import get_settings

        return get_settings().database_url
    except Exception:  # noqa: BLE001 - fall back to a narrower env read
        url = _read_database_url_from_env()
        if url:
            return url
        raise


def create_db_engine(url: str | None = None, **kwargs: object) -> Engine:
    """Create a SQLAlchemy :class:`Engine` for the resolved ``DATABASE_URL``."""
    return create_engine(url or get_database_url(), **kwargs)


def make_session_factory(engine: Engine | None = None) -> sessionmaker[Session]:
    """Return a configured :class:`sessionmaker` bound to ``engine``."""
    return sessionmaker(bind=engine or create_db_engine(), expire_on_commit=False)
