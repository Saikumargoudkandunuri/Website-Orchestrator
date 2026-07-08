# How to Run PostgreSQL Validation Tests

This guide shows how to run the full PostgreSQL validation once Docker is available.

## Prerequisites

1. Docker Desktop for Windows (or Docker Engine + Docker Compose)
2. `uv` package manager installed
3. Python 3.11+

## Step-by-Step Instructions

### 1. Start PostgreSQL Container

From the repository root:

```powershell
# Start the PostgreSQL service in detached mode
docker compose up -d db

# Verify the container is healthy
docker compose ps

# Check PostgreSQL logs if needed
docker compose logs db
```

Expected output from `docker compose ps`:
```
NAME                IMAGE               STATUS
wo_postgres         postgres:16-alpine  Up (healthy)
```

### 2. Verify Environment Configuration

Check that `.env` file exists and contains:

```env
DATABASE_URL=postgresql+psycopg://orchestrator:orchestrator@localhost:5432/orchestrator
TENANT_ID=default
# ... other variables
```

### 3. Run Alembic Migration

```powershell
cd packages\digital_twin

# Apply all migrations to PostgreSQL
uv run alembic upgrade head

# Verify current revision
uv run alembic current
```

Expected output:
```
INFO  [alembic.runtime.migration] Running upgrade  -> 0001_initial, initial Digital_Twin schema
0001_initial (head)
```

### 4. Verify Migration-Model Sync

This is the KEY TEST - it proves the migration and models are in sync.

```powershell
# Still in packages/digital_twin
uv run alembic revision --autogenerate -m "verify_sync"
```

**Expected Result**: The generated migration should contain **ONLY** `pass` in the `upgrade()` function.

**What to check**:

```python
def upgrade():
    pass  # ✓ GOOD - No operations means migration and models are in sync
```

If the migration contains actual operations (like `op.create_table`, `op.add_column`, etc.), that means the migration and models.py are OUT OF SYNC. You'll need to:
1. Compare the generated operations with models.py
2. Either update the migration or fix models.py
3. Delete the generated verification migration
4. Re-run this step until it produces an empty diff

### 5. Run Migration Sync Test Suite

```powershell
cd ..\..  # Back to repo root

# Run the migration sync tests
uv run pytest packages/digital_twin/tests/test_migration_sync.py -v
```

Expected output:
```
test_migration_model_sync_autogenerate_produces_empty_diff PASSED
test_migration_runs_successfully_on_empty_database PASSED

2 passed
```

### 6. Run All Digital Twin Tests

```powershell
uv run pytest packages/digital_twin/tests/ -v
```

Expected output:
```
39 passed
```

Watch for PostgreSQL-specific failures:
- Boolean handling issues
- DateTime timezone issues
- JSON/JSONB issues
- Constraint timing issues
- Sequence/autoincrement issues

### 7. Run Governance Service Tests

```powershell
uv run pytest packages/governance/tests/test_governance_service.py -v
```

Expected output:
```
47 passed
```

### 8. Run All DB-Backed Tests Together

```powershell
# Full test suite
uv run pytest packages/digital_twin/tests/ packages/governance/tests/test_governance_service.py -v
```

Expected output:
```
86 passed
```

## Troubleshooting

### Connection Failed

**Error**: `psycopg.OperationalError: connection failed`

**Fix**:
1. Verify PostgreSQL container is running: `docker compose ps`
2. Check PostgreSQL logs: `docker compose logs db`
3. Verify `.env` credentials match `docker-compose.yml`
4. Try connecting manually: `docker compose exec db psql -U orchestrator -d orchestrator`

### Password Authentication Failed

**Error**: `FATAL: password authentication failed for user "orchestrator"`

**Fix**:
1. Stop and remove the container: `docker compose down -v` (⚠️ This deletes data!)
2. Verify credentials in `.env` and `docker-compose.yml` match
3. Start fresh: `docker compose up -d db`

### Migration Already Applied

**Error**: `Target database is not up to date.`

**Fix**:
```powershell
# Check current version
uv run alembic current

# Downgrade if needed
uv run alembic downgrade base

# Re-apply migrations
uv run alembic upgrade head
```

### Boolean Type Mismatch

If you see failures related to boolean fields (`has_schema`, `reachable`, `ignored`):

**Symptom**: Values are `0`/`1` instead of `True`/`False`

**This should NOT happen** because models.py uses `Boolean` type which SQLAlchemy handles correctly. If it does happen, check:
1. Are you reading from the correct database connection?
2. Is SQLAlchemy configured correctly?
3. Is psycopg3 installed (not psycopg2)?

### DateTime Timezone Issues

If you see failures related to timestamp fields (`crawled_at`, `created_at`):

**Symptom**: Timestamps are naive (no timezone) or timezone comparison fails

**This should NOT happen** because models.py uses `DateTime(timezone=True)`. If it does happen, check:
1. Is the migration using `sa.DateTime(timezone=True)`?
2. Are timestamps being created with `timezone.utc`?
3. Is `_to_utc()` helper being used in repository.py?

## PostgreSQL-Specific Features to Test

Once all tests pass, you may want to manually verify PostgreSQL-specific features:

### 1. Check Table Structure

```powershell
docker compose exec db psql -U orchestrator -d orchestrator -c "\d pages"
```

Verify:
- `crawled_at` is `timestamp with time zone`
- `has_schema` is `boolean`
- `tenant_id` is indexed

### 2. Check Boolean Storage

```powershell
docker compose exec db psql -U orchestrator -d orchestrator
```

```sql
-- Insert a test page
INSERT INTO pages (id, tenant_id, url, word_count, has_schema, crawled_at)
VALUES ('test-id', 'test-tenant', 'http://test.com', 100, true, NOW());

-- Query it back
SELECT id, has_schema FROM pages WHERE id = 'test-id';
-- Should show: test-id | t (PostgreSQL boolean notation)

-- Cleanup
DELETE FROM pages WHERE id = 'test-id';
```

### 3. Check Timezone Handling

```sql
SELECT id, crawled_at, timezone('UTC', crawled_at) 
FROM pages 
LIMIT 1;
```

Should show timestamps are stored with timezone info.

## Success Criteria

PostgreSQL validation is COMPLETE when:

1. ✓ PostgreSQL container is running and healthy
2. ✓ Alembic migrations apply cleanly
3. ✓ `alembic revision --autogenerate` produces **EMPTY diff** (only `pass`)
4. ✓ All 39 digital_twin tests pass
5. ✓ All 47 governance tests pass  
6. ✓ Total: **86 tests pass** against PostgreSQL
7. ✓ No PostgreSQL-specific fixes were needed (or all fixes are documented)

## Updating the Status Document

After successful validation, update `POSTGRES_VALIDATION_STATUS.md`:

```markdown
## Current Status: COMPLETED ✓

### PostgreSQL Validation Results

- PostgreSQL container: RUNNING ✓
- Migration applied: SUCCESS ✓
- Autogenerate diff: EMPTY ✓
- Digital_Twin tests: 39 PASSED ✓
- Governance tests: 47 PASSED ✓
- Total: 86 PASSED ✓

### PostgreSQL-Specific Issues Found

[List any issues found and how they were fixed, or write "None"]

### Commit Message

"Task 1.3: Validated database integration against PostgreSQL

- All 86 DB-backed tests pass against real PostgreSQL
- Migration-model sync confirmed (autogenerate produces empty diff)
- No SQLite-specific assumptions found
- Schema works identically on both SQLite and PostgreSQL
- Tested: Boolean types, timezone-aware timestamps, tenant isolation, audit ordering"
```

## Rollback

If you need to stop PostgreSQL and clean up:

```powershell
# Stop container (keep data)
docker compose stop db

# Stop and remove container + data volume
docker compose down -v

# Remove .env if you want to start fresh
del .env
```
