# Pytest Collection Fix - Summary

## Problem

The monorepo had multiple packages with same-named `tests` directories:
- `packages/api/tests`
- `packages/check_engine/tests`
- `packages/core/tests`
- `packages/crawler/tests`
- `packages/digital_twin/tests`
- `packages/fix_generator/tests`
- `packages/governance/tests`
- `packages/publishing_adapter/tests`
- `apps/e2e/tests`

When running `pytest` from the repo root, these collided as pytest saw them all as the same `tests` module, causing collection failures.

## Solution

Added `--import-mode=importlib` to the pytest configuration in `pyproject.toml`.

This tells pytest to use Python's import system rather than prepending to `sys.path`, which resolves the module name collisions without requiring any changes to test files or directory structure.

## Change Made

**File**: `pyproject.toml`

**Change**:
```toml
[tool.pytest.ini_options]
addopts = "-ra --strict-markers --import-mode=importlib"  # Added --import-mode=importlib
```

## Verification

### Test Count Verification

**Per-package collection** (sum of individual runs):
- Digital Twin: 39 tests
- Governance: 61 tests  
- Crawler: 87 tests
- Check Engine: 29 tests
- Fix Generator: 7 tests
- Publishing Adapter: 49 tests
- API: 34 tests
- Core: 82 tests
- E2E: 7 tests
- **Total: 395 tests**

**Root-level collection**:
```powershell
PS> uv run pytest --collect-only -q
395 tests collected in 2.37s
```

✅ **Perfect match**: 395 tests collected both ways

### Test Execution Verification

**From root** (sample):
```powershell
PS> uv run pytest packages/core/tests/test_utils.py -v
47 passed in 0.51s
```

**Per-package** (sample):
```powershell
PS> cd packages\fix_generator
PS> uv run pytest -v
7 passed in 6.82s
```

✅ Both invocation methods work correctly

## Benefits

1. **Single command from root**: `uv run pytest` discovers and runs all 395 tests
2. **Per-package still works**: `cd packages/X && uv run pytest` unchanged
3. **No code changes**: Test files, imports, and logic untouched
4. **No directory restructuring**: No need to add `__init__.py` or rename directories
5. **Clean solution**: One config flag resolves the entire issue

## What `--import-mode=importlib` Does

- **Default mode (`prepend`)**: Pytest adds test directories to `sys.path`, causing `tests` modules to collide
- **`importlib` mode**: Pytest uses Python's standard import machinery, treating each `tests` directory as part of its package's namespace
- Result: `packages.api.tests`, `packages.core.tests`, etc. are distinct modules

## References

- Pytest docs: https://docs.pytest.org/en/stable/how-to/pythonpath.html#import-modes
- Issue solved: pytest import-mode collision in monorepos with same-named test directories
