"""Digital_Twin test configuration.

The Digital_Twin unit and property tests are written to be **hermetic**: each
one stands up a fresh in-memory SQLite database via ``create_engine("sqlite://")``
(the ORM uses generic column types, so no PostgreSQL or Docker is required). This
is what lets a single ``uv run pytest`` from the repository root run the entire
workspace with no external services — no package-by-package execution and no
manually-provisioned database.

Optional PostgreSQL validation
------------------------------
Running these same tests against a real PostgreSQL is available as an explicit,
opt-in step (used to prove production parity, see ``RUN_POSTGRES_TESTS.md``). It
is **off by default** so the ordinary root invocation never depends on external
infrastructure. To enable it, set ``WO_TEST_POSTGRES`` to a truthy value
(``1``/``true``/``yes``) and provide a PostgreSQL URL via ``WO_TEST_DATABASE_URL``
(preferred) or ``DATABASE_URL``::

    $env:WO_TEST_POSTGRES = "1"
    uv run pytest packages/digital_twin/tests/

When enabled, every ``create_engine("sqlite://")`` in the test modules is
transparently redirected to the configured PostgreSQL database, wiping and
recreating all tables per invocation to mimic SQLite's fresh in-memory isolation.
If the opt-in is set but the database is unreachable, the tests fall back to the
hermetic SQLite path instead of hard-failing the suite.

Note that the opt-in is intentionally **not** triggered by the mere presence of
``DATABASE_URL`` (which the application and ``.env`` always define); coupling the
default test run to that variable is exactly what previously prevented the root
``uv run pytest`` from running cleanly.
"""

from __future__ import annotations

import os
import sys
import warnings

import pytest
from sqlalchemy import create_engine as _real_create_engine
from sqlalchemy import text

from digital_twin.models import Base

# Truthy string values that enable the opt-in PostgreSQL validation path.
_TRUTHY = frozenset({"1", "true", "yes", "on"})


def _postgres_opt_in() -> bool:
    """Return whether the explicit PostgreSQL validation opt-in is enabled."""
    return os.environ.get("WO_TEST_POSTGRES", "").strip().lower() in _TRUTHY


def _configured_postgres_url() -> str | None:
    """Return the PostgreSQL URL for the opt-in path, or ``None``.

    Prefers the test-specific ``WO_TEST_DATABASE_URL`` so the validation target
    can differ from the application's ``DATABASE_URL``; falls back to
    ``DATABASE_URL``. Only PostgreSQL URLs qualify.
    """
    for var in ("WO_TEST_DATABASE_URL", "DATABASE_URL"):
        url = os.environ.get(var, "")
        if url.startswith("postgresql"):
            return url
    return None


def _reachable(url: str) -> bool:
    """Return whether ``url`` accepts a trivial connection right now.

    Used so the opt-in path degrades gracefully to hermetic SQLite when the
    configured PostgreSQL is not actually available, rather than erroring the
    whole suite.
    """
    engine = _real_create_engine(url)
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:  # noqa: BLE001 - any connection failure means "not reachable"
        return False
    finally:
        engine.dispose()


def _resolve_postgres_url() -> str | None:
    """Resolve the PostgreSQL URL to redirect to, honouring the opt-in.

    Returns ``None`` (meaning "run hermetically on SQLite") unless the opt-in is
    explicitly enabled, a PostgreSQL URL is configured, and that database is
    reachable.
    """
    if not _postgres_opt_in():
        return None
    url = _configured_postgres_url()
    if url is None:
        warnings.warn(
            "WO_TEST_POSTGRES is set but no PostgreSQL URL was found in "
            "WO_TEST_DATABASE_URL or DATABASE_URL; running on SQLite.",
            stacklevel=1,
        )
        return None
    if not _reachable(url):
        warnings.warn(
            "WO_TEST_POSTGRES is set but the configured PostgreSQL is not "
            "reachable; falling back to hermetic SQLite.",
            stacklevel=1,
        )
        return None
    return url


_pg_url = _resolve_postgres_url()

# Test modules that hardcode create_engine("sqlite://").
_MODULES_TO_PATCH = [
    "test_repository",
    "test_repository_edge_cases",
    "test_models_schema",
    "test_property_10_page_roundtrip",
    "test_property_11_freshness",
    "test_property_12_unknown_page",
    "test_property_19_ignored_exclusion",
    "test_property_56_tenant_id_column",
    "test_property_57_tenant_stamping",
]


@pytest.fixture(autouse=True)
def _redirect_sqlite_to_postgres(request, monkeypatch):
    """Redirect ``create_engine("sqlite://")`` to PostgreSQL only when opted in.

    In the default (hermetic) configuration ``_pg_url`` is ``None`` and this
    fixture is a no-op, so every test uses its own in-memory SQLite database. If
    the PostgreSQL opt-in is enabled and reachable, each ``create_engine("sqlite://")``
    is redirected to the configured database, which is wiped and recreated per
    invocation to reproduce SQLite's fresh-database isolation.

    The migration_sync tests manage their own engine/DB lifecycle and are excluded.
    """
    if _pg_url is None:
        yield
        return

    # Skip this fixture for migration_sync tests — they manage their own DB lifecycle.
    if "migration_sync" in request.node.nodeid:
        yield
        return

    engine = _real_create_engine(_pg_url)

    def _patched_create_engine(url, *args, **kwargs):
        if url == "sqlite://":
            # Wipe and recreate tables for full isolation (mimic fresh SQLite).
            Base.metadata.drop_all(engine, checkfirst=True)
            Base.metadata.create_all(engine, checkfirst=True)
            return engine
        return _real_create_engine(url, *args, **kwargs)

    # Patch create_engine in every loaded test module.
    for mod_suffix in _MODULES_TO_PATCH:
        for mod_name, mod_obj in sys.modules.items():
            if mod_obj is not None and mod_name.endswith(mod_suffix):
                if hasattr(mod_obj, "create_engine"):
                    monkeypatch.setattr(mod_obj, "create_engine", _patched_create_engine)

    yield

    # Final cleanup after test.
    Base.metadata.drop_all(engine, checkfirst=True)
    engine.dispose()
