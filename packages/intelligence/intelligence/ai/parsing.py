"""Robust JSON extraction from raw AI output (§9 parser tests).

LLMs frequently wrap JSON in markdown code fences, prepend prose, or get cut off
by a token limit mid-object. :func:`extract_json` handles the common cases and
cleanly returns ``None`` for anything unrecoverable — it never raises on bad
input, so a malformed model response degrades to a validation failure rather
than crashing the analysis.
"""

from __future__ import annotations

import json
import re
from typing import Any

__all__ = ["extract_json", "strip_code_fences"]

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def strip_code_fences(text: str) -> str:
    """Return the contents of the first ```json ...``` fence, or ``text`` as-is."""
    match = _FENCE_RE.search(text)
    if match:
        return match.group(1).strip()
    return text.strip()


def extract_json(text: str) -> Any | None:
    """Best-effort parse of a JSON object/array from ``text``.

    Strategy, in order:

    1. direct ``json.loads`` of the (fence-stripped) text;
    2. parse of the first balanced ``{...}`` / ``[...]`` span found;
    3. a lenient recovery that closes an unclosed trailing brace/bracket (for
       token-truncated output).

    Returns the parsed value, or ``None`` when nothing usable can be recovered.
    Never raises.
    """
    if not text or not text.strip():
        return None

    candidate = strip_code_fences(text)

    # 1. Direct parse.
    parsed = _try_load(candidate)
    if parsed is not None:
        return parsed

    # 2. First balanced object/array span.
    span = _first_json_span(candidate)
    if span is not None:
        parsed = _try_load(span)
        if parsed is not None:
            return parsed
        # 3. Lenient close of a truncated span.
        repaired = _repair_truncated(span)
        if repaired is not None:
            parsed = _try_load(repaired)
            if parsed is not None:
                return parsed

    return None


def _try_load(text: str) -> Any | None:
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        return None


def _first_json_span(text: str) -> str | None:
    """Return the substring from the first ``{``/``[`` to its matching close.

    If no matching close exists (truncated), returns from the opener to the end
    so :func:`_repair_truncated` can attempt to close it.
    """
    start = _first_index(text, "{", "[")
    if start is None:
        return None
    opener = text[start]
    closer = "}" if opener == "{" else "]"
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == opener:
            depth += 1
        elif ch == closer:
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return text[start:]  # truncated — no matching close


def _first_index(text: str, *chars: str) -> int | None:
    positions = [text.find(c) for c in chars]
    positions = [p for p in positions if p >= 0]
    return min(positions) if positions else None


def _repair_truncated(span: str) -> str | None:
    """Close unbalanced braces/brackets in a truncated JSON span, best-effort."""
    # Drop a dangling trailing comma or partial key/value fragment.
    trimmed = span.rstrip()
    trimmed = re.sub(r",\s*$", "", trimmed)
    # If we're mid-string (odd number of unescaped quotes), give up.
    if _unescaped_quote_count(trimmed) % 2 != 0:
        return None
    opens = trimmed.count("{") - trimmed.count("}")
    bopens = trimmed.count("[") - trimmed.count("]")
    if opens < 0 or bopens < 0:
        return None
    return trimmed + ("]" * bopens) + ("}" * opens)


def _unescaped_quote_count(text: str) -> int:
    count = 0
    escape = False
    for ch in text:
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            count += 1
    return count
