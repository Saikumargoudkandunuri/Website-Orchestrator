"""Structural JSON-schema validation (§7).

A small, dependency-free validator for the subset of JSON Schema the prompt
templates declare: ``object`` (with ``properties``/``required``), ``array``
(with ``items``), and the scalar types ``string``/``number``/``integer``/
``boolean``. It rejects structurally wrong AI output (missing required fields,
wrong types) so the orchestrator can retry before anything reaches persistence.
"""

from __future__ import annotations

from typing import Any

from intelligence.validation.context import ValidationContext
from intelligence.validation.result import ValidatorOutcome

__all__ = ["JsonSchemaValidator", "validate_against_schema"]

_TYPE_CHECKS = {
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "string": lambda v: isinstance(v, str),
    "boolean": lambda v: isinstance(v, bool),
    # bool is a subclass of int; exclude it from number/integer.
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
}


def validate_against_schema(value: Any, schema: dict[str, Any], path: str = "$") -> list[str]:
    """Return a list of human-readable validation errors (empty when valid)."""
    errors: list[str] = []
    expected = schema.get("type")
    if expected is not None:
        check = _TYPE_CHECKS.get(expected)
        if check is not None and not check(value):
            errors.append(f"{path}: expected {expected}, got {type(value).__name__}")
            return errors  # type mismatch: don't descend further

    if expected == "object":
        for key in schema.get("required", []):
            if key not in value:
                errors.append(f"{path}: missing required field '{key}'")
        props = schema.get("properties", {})
        for key, subschema in props.items():
            if key in value:
                errors.extend(
                    validate_against_schema(value[key], subschema, f"{path}.{key}")
                )
    elif expected == "array":
        item_schema = schema.get("items")
        if item_schema:
            for i, item in enumerate(value):
                errors.extend(
                    validate_against_schema(item, item_schema, f"{path}[{i}]")
                )
    return errors


class JsonSchemaValidator:
    """Validates a parsed AI payload against a prompt's declared schema."""

    def __init__(self, schema: dict[str, Any]) -> None:
        self._schema = schema

    def validate(
        self, payload: Any, *, context: ValidationContext | None = None
    ) -> ValidatorOutcome:
        if payload is None:
            return ValidatorOutcome(ok=False, errors=["payload is not valid JSON"])
        errors = validate_against_schema(payload, self._schema)
        return ValidatorOutcome(ok=not errors, errors=errors, payload=payload)
