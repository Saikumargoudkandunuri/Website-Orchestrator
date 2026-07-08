"""Property test for shared trace id across one operation.

Feature: website-orchestrator-milestone-0, Property 52: All logs within one
operation share a trace id.

Validates: Requirements 13.2
"""

from __future__ import annotations

import io
import json

from hypothesis import given, settings
from hypothesis import strategies as st

from core import logging as wo_logging


def _entries(buffer: io.StringIO) -> list[dict]:
    """Parse each non-empty line of the buffer as one JSON object."""
    return [json.loads(line) for line in buffer.getvalue().splitlines() if line.strip()]


# Arbitrary log messages: any text (structlog stores it under the ``event`` key).
_messages = st.lists(st.text(), min_size=1, max_size=20)


@settings(max_examples=100)
@given(first_messages=_messages, second_messages=_messages)
def test_property_52_all_logs_within_one_operation_share_a_trace_id(
    first_messages: list[str],
    second_messages: list[str],
) -> None:
    """Property 52: every entry emitted within a single ``operation_trace``
    block carries the same ``trace_id`` (equal to the id the context manager
    yields), and two separate operations receive distinct trace ids.

    Validates: Requirements 13.2
    """
    # Fresh in-memory buffer per example so runs never bleed into one another.
    buffer = io.StringIO()
    wo_logging.configure_logging(stream=buffer)
    log = wo_logging.get_logger("property-52")

    # --- First operation: emit an arbitrary number of arbitrary messages. ---
    with wo_logging.operation_trace() as first_trace_id:
        for message in first_messages:
            log.info(message)

    # --- Second, separate operation. ---
    with wo_logging.operation_trace() as second_trace_id:
        for message in second_messages:
            log.info(message)

    entries = _entries(buffer)

    # One entry per log call, in order.
    assert len(entries) == len(first_messages) + len(second_messages)

    first_count = len(first_messages)
    first_entries = entries[:first_count]
    second_entries = entries[first_count:]

    # Every entry within one operation shares the yielded trace id.
    for entry in first_entries:
        assert entry[wo_logging.TRACE_ID_KEY] == first_trace_id
    for entry in second_entries:
        assert entry[wo_logging.TRACE_ID_KEY] == second_trace_id

    # All trace ids within a single operation are identical.
    assert len({e[wo_logging.TRACE_ID_KEY] for e in first_entries}) == 1
    assert len({e[wo_logging.TRACE_ID_KEY] for e in second_entries}) == 1

    # Separate operations get distinct trace ids.
    assert first_trace_id != second_trace_id
