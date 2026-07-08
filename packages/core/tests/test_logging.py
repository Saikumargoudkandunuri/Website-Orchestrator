"""Tests for Core_Package structured logging (Req 13.1, 13.2, 13.4, 13.5)."""

from __future__ import annotations

import io
import json

import pytest

from core import logging as wo_logging
from core.utils import REDACTION_PLACEHOLDER


def _configure_to_buffer(secret_values=None) -> io.StringIO:
    """Configure logging to render into an in-memory buffer for assertions."""
    buffer = io.StringIO()
    wo_logging.configure_logging(secret_values=secret_values, stream=buffer)
    return buffer


def _entries(buffer: io.StringIO) -> list[dict]:
    """Parse each non-empty line of the buffer as one JSON object."""
    return [json.loads(line) for line in buffer.getvalue().splitlines() if line.strip()]


def test_imports_are_available() -> None:
    # The public surface the rest of the platform relies on must be importable.
    assert callable(wo_logging.get_logger)
    assert callable(wo_logging.configure_logging)
    assert callable(wo_logging.operation_trace)
    assert wo_logging.TRACE_ID_KEY == "trace_id"


def test_entry_is_single_line_json_with_required_fields() -> None:
    # Req 13.1: each entry is a single JSON object with timestamp, level,
    # message, and a trace id.
    buffer = _configure_to_buffer()
    log = wo_logging.get_logger("test")
    with wo_logging.operation_trace() as trace_id:
        log.info("hello world", foo="bar")

    raw = buffer.getvalue()
    lines = [line for line in raw.splitlines() if line.strip()]
    assert len(lines) == 1  # single line
    assert "\n" not in lines[0]

    entry = json.loads(lines[0])
    assert entry["timestamp"]
    assert entry["level"] == "info"
    assert entry["event"] == "hello world"
    assert entry[wo_logging.TRACE_ID_KEY] == trace_id
    assert entry["foo"] == "bar"


def test_entries_in_one_operation_share_trace_id() -> None:
    # Req 13.2: all entries produced during one operation share a trace id.
    buffer = _configure_to_buffer()
    log = wo_logging.get_logger("test")
    with wo_logging.operation_trace() as trace_id:
        log.info("first")
        log.info("second")

    entries = _entries(buffer)
    assert len(entries) == 2
    assert entries[0][wo_logging.TRACE_ID_KEY] == trace_id
    assert entries[1][wo_logging.TRACE_ID_KEY] == trace_id


def test_separate_operations_get_distinct_trace_ids() -> None:
    buffer = _configure_to_buffer()
    log = wo_logging.get_logger("test")
    with wo_logging.operation_trace() as first_id:
        log.info("a")
    with wo_logging.operation_trace() as second_id:
        log.info("b")

    assert first_id != second_id
    entries = _entries(buffer)
    assert entries[0][wo_logging.TRACE_ID_KEY] == first_id
    assert entries[1][wo_logging.TRACE_ID_KEY] == second_id


def test_secret_value_is_redacted_while_other_fields_retained() -> None:
    # Req 13.4 / 13.5: a credential value in a payload is redacted, everything
    # else is retained.
    secret = "super-secret-app-password"
    buffer = _configure_to_buffer(secret_values=[secret])
    log = wo_logging.get_logger("test")
    with wo_logging.operation_trace():
        log.info(
            "publishing",
            password=secret,
            note=f"used {secret} to authenticate",
            user="editor",
        )

    entry = _entries(buffer)[0]
    assert entry["password"] == REDACTION_PLACEHOLDER
    assert secret not in entry["note"]
    assert REDACTION_PLACEHOLDER in entry["note"]
    assert entry["user"] == "editor"  # non-secret content retained
    assert entry["event"] == "publishing"


def test_configure_never_requires_loadable_config() -> None:
    # Importing/configuring logging must not crash when settings are absent.
    buffer = _configure_to_buffer(secret_values=None)
    log = wo_logging.get_logger("test")
    with wo_logging.operation_trace():
        log.info("no config needed")
    assert _entries(buffer)[0]["event"] == "no config needed"


def test_bind_and_clear_trace_id_helpers() -> None:
    buffer = _configure_to_buffer()
    log = wo_logging.get_logger("test")
    tid = wo_logging.bind_trace_id()
    try:
        log.info("bound")
    finally:
        wo_logging.clear_trace_id()
    log.info("unbound")

    entries = _entries(buffer)
    assert entries[0][wo_logging.TRACE_ID_KEY] == tid
    assert wo_logging.TRACE_ID_KEY not in entries[1]
