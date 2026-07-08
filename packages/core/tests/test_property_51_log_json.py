"""Property-based test for well-formed JSON log entries.

Feature: website-orchestrator-milestone-0, Property 51: Every log entry is a
single well-formed JSON object.

Validates: Requirements 13.1
"""

from __future__ import annotations

import io
import json

from hypothesis import given, settings
from hypothesis import strategies as st

from core import logging as wo_logging

# JSON-safe scalar values that can appear as structured field payloads.
_json_scalars = st.one_of(
    st.text(),
    st.booleans(),
    st.none(),
    st.integers(min_value=-(10**9), max_value=10**9),
    st.floats(allow_nan=False, allow_infinity=False, width=32),
)

# Arbitrary structured key/value fields (dicts of JSON-safe values). Field keys
# must not collide with the reserved entry keys the renderer populates itself.
_reserved_keys = {"event", "level", "timestamp", wo_logging.TRACE_ID_KEY}
_field_keys = st.text(min_size=1).filter(lambda k: k not in _reserved_keys)
_fields = st.dictionaries(keys=_field_keys, values=_json_scalars, max_size=6)

# Varied messages: unicode, punctuation, whitespace, emptiness all allowed.
_messages = st.text()


@settings(max_examples=100)
@given(
    calls=st.lists(st.tuples(_messages, _fields), min_size=1, max_size=8),
)
def test_property_51_every_log_entry_is_single_wellformed_json(calls) -> None:
    """Each emitted log entry is exactly one line and one well-formed JSON object.

    Feature: website-orchestrator-milestone-0, Property 51: Every log entry is a
    single well-formed JSON object.

    Validates: Requirements 13.1
    """
    # Fresh in-memory buffer per example keeps examples independent.
    buffer = io.StringIO()
    wo_logging.configure_logging(stream=buffer)
    log = wo_logging.get_logger("property-51")

    # Emit every generated (message, fields) pair inside one operation trace.
    with wo_logging.operation_trace():
        for message, fields in calls:
            log.info(message, **fields)

    raw = buffer.getvalue()
    lines = raw.splitlines()

    # One emitted line per log call (count of lines == count of log calls).
    assert len(lines) == len(calls)

    for line, (message, _fields) in zip(lines, calls):
        # A single entry must be exactly one line: no embedded newlines.
        assert "\n" not in line

        # Each line parses as a single well-formed JSON object (a dict).
        entry = json.loads(line)
        assert isinstance(entry, dict)

        # At minimum: timestamp, level, and message (event) are present.
        assert "timestamp" in entry
        assert entry["timestamp"]
        assert entry["level"] == "info"
        assert "event" in entry
        assert entry["event"] == message
