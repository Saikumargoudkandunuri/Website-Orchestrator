# Running Tests from Repository Root

## Quick Reference

### Run all tests from root
```powershell
uv run pytest
```

### Run all tests with output
```powershell
uv run pytest -v
```

### Run specific package from root
```powershell
uv run pytest packages/digital_twin/tests/
```

### Run specific test file from root
```powershell
uv run pytest packages/core/tests/test_utils.py
```

### Per-package invocation (still works)
```powershell
cd packages/digital_twin
uv run pytest
```

## Test Counts (Total: 395)

| Package               | Test Count |
|-----------------------|------------|
| Digital Twin          | 39         |
| Governance            | 61         |
| Crawler               | 87         |
| Check Engine          | 29         |
| Fix Generator         | 7          |
| Publishing Adapter    | 49         |
| API                   | 34         |
| Core                  | 82         |
| E2E                   | 7          |
| **Total**             | **395**    |

## How It Works

The fix uses `--import-mode=importlib` in `pyproject.toml`, which tells pytest to use Python's standard import system instead of path manipulation. This allows multiple packages to have same-named `tests` directories without collision.

Each `tests` directory is treated as part of its parent package's namespace:
- `packages.api.tests`
- `packages.core.tests`
- `packages.digital_twin.tests`
- etc.

## Troubleshooting

### If you see "ModuleNotFoundError" for a test module

Make sure you're running from the repository root or have the correct working directory.

### Database availability

No action needed. The suite is **hermetic by default**: the Digital_Twin tests
run against in-memory SQLite regardless of whether `DATABASE_URL` is set, so a
single `uv run pytest` from the root runs the whole workspace with no Docker or
external PostgreSQL. You no longer need to clear `DATABASE_URL` or remove `.env`.

To optionally validate the Digital_Twin tests against a real PostgreSQL, opt in
explicitly:

```powershell
$env:WO_TEST_POSTGRES = "1"
# PostgreSQL URL comes from WO_TEST_DATABASE_URL (preferred) or DATABASE_URL
uv run pytest packages/digital_twin/tests/
```

If the opt-in is set but PostgreSQL is unreachable, the tests fall back to the
hermetic SQLite path instead of failing.

### Running only fast tests

```powershell
# Skip property-based tests (Hypothesis)
uv run pytest -m "not property"

# Skip e2e tests
uv run pytest --ignore=apps/e2e/
```

## What Changed

**Before**: Running `pytest` from root caused module name collisions because all packages had a `tests` directory.

**After**: One config line fix in `pyproject.toml`:
```toml
[tool.pytest.ini_options]
addopts = "-ra --strict-markers --import-mode=importlib"
```

No test files changed. No directory structure changed. Just works.
