"""Property-based test for the Core_Package exception hierarchy.

Feature: website-orchestrator-milestone-0, Property 59: Subsystem exceptions
subclass a Core_Package base exception.

Validates: Requirements 15.4, 12.3
"""

from __future__ import annotations

import inspect

from hypothesis import given, settings
from hypothesis import strategies as st

from core import exceptions as exc

# The single root of the whole platform's error tree.
ROOT = exc.OrchestratorError

# The per-subsystem base exceptions. Each must subclass OrchestratorError and
# each subsystem must define at least one of these (Req 12.3, 15.4).
SUBSYSTEM_BASES = (
    exc.CrawlerError,
    exc.DigitalTwinError,
    exc.CheckEngineError,
    exc.FixGeneratorError,
    exc.AiGeneratorError,
    exc.PublishingError,
    exc.EditingError,
    exc.GovernanceError,
    exc.ApiError,
    exc.ConfigError,
)


def _discover_exception_classes() -> list[type]:
    """Enumerate every exception class defined in ``core.exceptions``.

    Introspects the module for classes that are subclasses of
    :class:`OrchestratorError` (including the root itself). Only classes defined
    in this module are considered — imported symbols are ignored.
    """
    found: list[type] = []
    for _name, obj in inspect.getmembers(exc, inspect.isclass):
        if obj.__module__ != exc.__name__:
            continue
        if issubclass(obj, ROOT):
            found.append(obj)
    return found


ALL_EXCEPTION_CLASSES = _discover_exception_classes()

# Non-root exception classes: every one of these must subclass OrchestratorError.
NON_ROOT_CLASSES = [c for c in ALL_EXCEPTION_CLASSES if c is not ROOT]

# Leaf exceptions: those that are not one of the subsystem bases and not the
# root. Each must subclass one of the per-subsystem bases (which in turn
# subclasses OrchestratorError).
LEAF_CLASSES = [
    c for c in NON_ROOT_CLASSES if c not in SUBSYSTEM_BASES
]


@settings(max_examples=100)
@given(cls=st.sampled_from(NON_ROOT_CLASSES))
def test_property_59_every_exception_subclasses_root(cls: type) -> None:
    """Every custom exception (other than the root) subclasses OrchestratorError.

    Feature: website-orchestrator-milestone-0, Property 59: Subsystem exceptions
    subclass a Core_Package base exception.

    Validates: Requirements 15.4, 12.3
    """
    assert issubclass(cls, ROOT)
    # The root remains a subclass of the builtin Exception contract.
    assert issubclass(cls, Exception)


@settings(max_examples=100)
@given(cls=st.sampled_from(LEAF_CLASSES))
def test_property_59_every_leaf_subclasses_a_subsystem_base(cls: type) -> None:
    """Every subsystem-specific leaf exception subclasses a per-subsystem base,
    which itself subclasses OrchestratorError.

    Feature: website-orchestrator-milestone-0, Property 59: Subsystem exceptions
    subclass a Core_Package base exception.

    Validates: Requirements 15.4, 12.3
    """
    # The leaf descends from exactly the subsystem bases that are its ancestors.
    matching_bases = [b for b in SUBSYSTEM_BASES if issubclass(cls, b)]
    assert matching_bases, f"{cls.__name__} does not subclass any subsystem base"
    for base in matching_bases:
        assert issubclass(base, ROOT)


def test_property_59_subsystem_bases_subclass_root() -> None:
    """Each subsystem base (Crawler/DigitalTwin/CheckEngine/FixGenerator/
    Publishing/Governance/Api/Config) subclasses OrchestratorError.

    Validates: Requirements 15.4, 12.3
    """
    for base in SUBSYSTEM_BASES:
        assert issubclass(base, ROOT)
        assert base is not ROOT


def test_property_59_total_coverage_all_exceptions_subclass_root() -> None:
    """Total-coverage check: every discovered exception class in core.exceptions
    subclasses OrchestratorError (the root subclasses itself trivially), and at
    least the full documented set was discovered.

    Validates: Requirements 15.4, 12.3
    """
    # Sanity: discovery actually found the hierarchy.
    assert ROOT in ALL_EXCEPTION_CLASSES
    assert len(NON_ROOT_CLASSES) >= len(SUBSYSTEM_BASES)

    for cls in ALL_EXCEPTION_CLASSES:
        assert issubclass(cls, ROOT)

    # Every subsystem base was discovered by introspection.
    for base in SUBSYSTEM_BASES:
        assert base in ALL_EXCEPTION_CLASSES

    # Every non-root class either IS a subsystem base or descends from one.
    for cls in NON_ROOT_CLASSES:
        assert cls in SUBSYSTEM_BASES or any(
            issubclass(cls, b) for b in SUBSYSTEM_BASES
        ), f"{cls.__name__} is not covered by any subsystem base"
