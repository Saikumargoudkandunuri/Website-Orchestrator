"""Property 58: Core_Package imports nothing internal.

Feature: website-orchestrator-milestone-0, Property 58: Core_Package imports
nothing internal

Validates: Requirements 15.2, 15.6

Requirement 15.2 states that Core_Package SHALL NOT import or depend on any other
subsystem or package in the Website_Orchestrator, and Requirement 15.6 states
that a dependency pointing from Core_Package outward to any other subsystem is an
invalid dependency direction. Dependencies point inward toward Core_Package and
never outward from it.

This property parses the abstract syntax tree of every Python source module in
``packages/core/core`` and asserts that none of their import statements reference
an internal subsystem package, and that no relative import escapes the ``core``
package itself.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

# The directory holding the Core_Package source modules:
# .../packages/core/tests/this_file.py -> .../packages/core/core
CORE_PACKAGE_DIR = Path(__file__).resolve().parent.parent / "core"

# Top-level import names that belong to other subsystems of the orchestrator.
# Core_Package must never import from any of these (Requirement 15.2 / 15.6).
FORBIDDEN_INTERNAL_TOP_LEVEL = frozenset(
    {
        "crawler",
        "digital_twin",
        "check_engine",
        "fix_generator",
        "publishing_adapter",
        "governance",
        "api",
    }
)


def _collect_core_modules() -> list[Path]:
    """Enumerate every Python source file that makes up Core_Package."""
    return sorted(CORE_PACKAGE_DIR.glob("*.py"))


CORE_MODULES = _collect_core_modules()


def _top_level_name(dotted: str) -> str:
    """Return the first path segment of a dotted module name (``a.b.c`` -> ``a``)."""
    return dotted.split(".", 1)[0]


def _imported_targets(tree: ast.AST) -> list[tuple[str, int, str | None]]:
    """Extract import targets from an AST as (top_level_name, level, raw) tuples.

    - ``import a.b`` and ``import a.b as c`` yield ("a", 0, "a.b").
    - ``from a.b import c`` yields ("a", 0, "a.b").
    - ``from . import x`` / ``from .foo import y`` yield the relative import with
      its level so escapes above the package can be detected.
    """
    targets: list[tuple[str, int, str | None]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                targets.append((_top_level_name(alias.name), 0, alias.name))
        elif isinstance(node, ast.ImportFrom):
            module = node.module  # may be None for ``from . import x``
            top = _top_level_name(module) if module else None
            targets.append((top or "", node.level, module))
    return targets


def test_property_58_core_package_has_source_modules() -> None:
    """Guard: the property is meaningless if no core modules are discovered."""
    assert CORE_MODULES, f"No core modules found under {CORE_PACKAGE_DIR}"


def _assert_module_imports_nothing_internal(module_path: Path) -> None:
    """Assert a single core module imports no internal subsystem."""
    source = module_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(module_path))

    for top_level, level, raw in _imported_targets(tree):
        # Absolute imports must not target a forbidden internal subsystem.
        if level == 0:
            assert top_level not in FORBIDDEN_INTERNAL_TOP_LEVEL, (
                f"{module_path.name} imports internal subsystem "
                f"'{top_level}' (from '{raw}'); Core_Package must not depend on "
                f"other subsystems (Requirements 15.2, 15.6)."
            )
        else:
            # Relative imports: level 1 stays within `core`. A level of 2+ would
            # escape the `core` package and reach a sibling/parent, which is a
            # forbidden outward dependency.
            assert level == 1, (
                f"{module_path.name} uses a relative import (level={level}, "
                f"module='{raw}') that escapes the 'core' package; Core_Package "
                f"must not depend on other subsystems (Requirements 15.2, 15.6)."
            )


# Drawing varied, unique subsets of the core modules gives a large enough input
# space (combinations and orderings of the module set) for Hypothesis to run the
# full >= 100 examples required by the design, while every example still checks
# only real Core_Package source modules.
@settings(max_examples=100)
@given(
    module_paths=st.lists(
        st.sampled_from(CORE_MODULES),
        min_size=1,
        max_size=len(CORE_MODULES),
        unique=True,
    )
)
def test_property_58_core_imports_nothing_internal(module_paths: list[Path]) -> None:
    """For every core module, no import references an internal subsystem.

    Feature: website-orchestrator-milestone-0, Property 58: Core_Package imports
    nothing internal
    Validates: Requirements 15.2, 15.6
    """
    for module_path in module_paths:
        _assert_module_imports_nothing_internal(module_path)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-v"]))
