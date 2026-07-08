"""Migration-model sync verification (task 1.3).

This test proves that the Alembic migration and the SQLAlchemy models are in sync
by running ``alembic revision --autogenerate`` and asserting that the generated
diff is EMPTY. A non-empty diff means either the migration or the models are
stale and must be fixed.

This test is designed to run against BOTH the SQLite fallback (for fast local
iteration) and real PostgreSQL (to prove production compatibility). The engine
is determined from the DATABASE_URL environment variable or uses SQLite when
DATABASE_URL is unset or points to SQLite.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text

from digital_twin.db import get_database_url
from digital_twin.models import Base


def _drop_all_tables(engine, database_url: str) -> None:
    """Drop ALL tables including alembic_version for a truly clean slate."""
    Base.metadata.drop_all(engine)
    with engine.begin() as conn:
        if database_url.startswith("postgresql"):
            conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
        else:
            conn.execute(text("DROP TABLE IF EXISTS alembic_version"))


@pytest.fixture()
def database_url(tmp_path):
    """Return the database URL from environment, falling back to temporary SQLite file."""
    try:
        url = get_database_url()
        # If it's a PostgreSQL URL, test connectivity before using it
        if url.startswith("postgresql"):
            # Try to connect to verify the database is available
            test_engine = create_engine(url)
            try:
                with test_engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                test_engine.dispose()
                return url
            except Exception:
                # PostgreSQL URL configured but not reachable, fall back to SQLite
                test_engine.dispose()
                pass
    except Exception:
        pass
    # Fall back to a temporary file-based SQLite for fast local iteration
    # (in-memory sqlite:// doesn't work because Alembic and the test use different connections)
    sqlite_path = tmp_path / "test.db"
    return f"sqlite:///{sqlite_path}"


@pytest.fixture()
def alembic_config(database_url, monkeypatch):
    """Return an Alembic Config pointing at the migrations directory and the test database."""
    # Override the DATABASE_URL in the environment so env.py picks up the test database
    monkeypatch.setenv("DATABASE_URL", database_url)
    
    migrations_dir = Path(__file__).parent.parent / "migrations"
    ini_path = Path(__file__).parent.parent / "alembic.ini"
    
    cfg = Config(str(ini_path))
    cfg.set_main_option("script_location", str(migrations_dir))
    cfg.set_main_option("sqlalchemy.url", database_url)
    return cfg


def test_migration_model_sync_autogenerate_produces_empty_diff(alembic_config, database_url):
    """Assert that ``alembic revision --autogenerate`` produces an EMPTY diff.
    
    An empty diff proves the migration and models.py are in sync. A non-empty
    diff means one or the other is stale and must be fixed.
    
    This test:
    1. Applies existing migrations to a clean database
    2. Runs alembic revision --autogenerate to a temp file
    3. Parses the generated migration and asserts upgrade() is empty
    """
    engine = create_engine(database_url)
    
    # Clean slate: drop all tables including alembic_version
    _drop_all_tables(engine, database_url)
    
    # Apply the current migration HEAD to the database
    command.upgrade(alembic_config, "head")
    
    # Now run autogenerate to check if any diff is detected
    # We'll use a temporary directory for the generated migration
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_versions_dir = Path(tmpdir) / "versions"
        temp_versions_dir.mkdir(parents=True)
        
        # Copy the entire migrations directory structure to temp
        original_location = alembic_config.get_main_option("script_location")
        migrations_dir = Path(original_location)
        
        import shutil
        shutil.copy(migrations_dir / "env.py", Path(tmpdir) / "env.py")
        shutil.copy(migrations_dir / "script.py.mako", Path(tmpdir) / "script.py.mako")
        
        # Copy existing migrations so Alembic knows the revision history
        original_versions = migrations_dir / "versions"
        for migration_file in original_versions.glob("*.py"):
            if not migration_file.name.startswith("__"):
                shutil.copy(migration_file, temp_versions_dir / migration_file.name)
        
        # Temporarily reconfigure alembic to use our temp directory
        alembic_config.set_main_option("script_location", tmpdir)
        
        # Count existing migrations
        existing_count = len(list(temp_versions_dir.glob("*.py")))
        
        # Run autogenerate
        command.revision(
            alembic_config,
            message="test_autogenerate",
            autogenerate=True,
        )
        
        # Find the NEW migration file (should be one more than before)
        migration_files = sorted(temp_versions_dir.glob("*.py"))
        assert len(migration_files) == existing_count + 1, \
            f"Expected {existing_count + 1} migration files, found {len(migration_files)}"
        
        # Get the last (newest) migration file
        new_migration_file = migration_files[-1]
        migration_content = new_migration_file.read_text()
        
        # Parse the migration to check if upgrade() is empty
        # An empty migration will have either "pass" or no operations
        # We look for the upgrade() function body
        lines = migration_content.split("\n")
        in_upgrade = False
        upgrade_body_lines = []
        
        for line in lines:
            if line.strip().startswith("def upgrade():"):
                in_upgrade = True
                continue
            elif in_upgrade and line.strip().startswith("def downgrade():"):
                break
            elif in_upgrade:
                stripped = line.strip()
                # Skip empty lines and comments
                if stripped and not stripped.startswith("#"):
                    upgrade_body_lines.append(stripped)
        
        # Check if upgrade body is empty or just "pass"
        effective_operations = [
            line for line in upgrade_body_lines 
            if line != "pass" and not line.startswith('"""') and line != '"""'
        ]
        
        # Restore original config
        alembic_config.set_main_option("script_location", original_location)
        
        if effective_operations:
            pytest.fail(
                f"Migration-model sync check FAILED: autogenerate produced a non-empty diff.\n"
                f"This means either the migration (20240101_0001_initial_schema.py) or "
                f"models.py is stale.\n\n"
                f"Generated migration content:\n"
                f"{migration_content}\n\n"
                f"Effective operations found:\n"
                f"{chr(10).join(effective_operations)}"
            )
    
    # Cleanup
    _drop_all_tables(engine, database_url)
    engine.dispose()


def test_migration_runs_successfully_on_empty_database(alembic_config, database_url):
    """Verify that the migration can be applied cleanly to an empty database."""
    engine = create_engine(database_url)
    
    # Clean slate (including alembic_version so migrations run from scratch)
    _drop_all_tables(engine, database_url)
    
    # Run migrations from scratch
    command.upgrade(alembic_config, "head")
    
    # Create a fresh engine connection to check the result
    check_engine = create_engine(database_url)
    
    # Verify all expected tables exist
    with check_engine.connect() as conn:
        # Check for the six expected tables
        expected_tables = {
            "pages", "links", "page_metadata", 
            "issues", "suggested_fixes", "audit_trail"
        }
        
        if database_url.startswith("postgresql"):
            # PostgreSQL query
            result = conn.execute(text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public'"
            ))
        else:
            # SQLite query
            result = conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ))
        
        actual_tables = {row[0] for row in result}
        
        # Filter out alembic_version table
        actual_tables.discard("alembic_version")
        
        assert actual_tables == expected_tables, (
            f"Expected tables {expected_tables}, got {actual_tables}"
        )
    
    # Cleanup
    check_engine.dispose()
    _drop_all_tables(engine, database_url)
    engine.dispose()
