"""Dotted-path access into nested Pydantic models (§4.12, §13.3).

Used by both the immutability enforcement (reject a proposal targeting a locked
``immutable_fields`` path) and the override carry-forward (copy a human-overridden
field path from the prior KnowledgeObject version into the next). Kept as a tiny,
pure utility so both concerns share one correct implementation.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

__all__ = ["get_by_path", "set_by_path", "path_matches_any"]

_MISSING = object()


def get_by_path(obj: Any, path: str) -> Any:
    """Return the value at dotted ``path`` within ``obj``, or ``None`` if absent."""
    current = obj
    for part in path.split("."):
        if isinstance(current, BaseModel):
            current = getattr(current, part, _MISSING)
        elif isinstance(current, dict):
            current = current.get(part, _MISSING)
        else:
            return None
        if current is _MISSING:
            return None
    return current


def set_by_path(obj: Any, path: str, value: Any) -> bool:
    """Set the value at dotted ``path`` within ``obj``. Returns ``True`` on success.

    Only traverses Pydantic models (their attributes are mutable by default);
    returns ``False`` if the path cannot be resolved rather than raising.
    """
    parts = path.split(".")
    current = obj
    for part in parts[:-1]:
        if isinstance(current, BaseModel):
            current = getattr(current, part, _MISSING)
        else:
            return False
        if current is _MISSING or current is None:
            return False
    leaf = parts[-1]
    if isinstance(current, BaseModel) and leaf in type(current).model_fields:
        setattr(current, leaf, value)
        return True
    return False


def path_matches_any(path: str, locked: list[str]) -> bool:
    """Return ``True`` if ``path`` equals or is nested under any ``locked`` path.

    So locking ``content_intelligence.first_paragraph`` also blocks a write to
    ``content_intelligence.first_paragraph.anything`` deeper.
    """
    for lock in locked:
        if path == lock or path.startswith(lock + "."):
            return True
    return False
