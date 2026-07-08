"""Parser tests (§9): AI raw-output JSON parsing, including hostile inputs."""

from __future__ import annotations

from intelligence.ai.parsing import extract_json, strip_code_fences


def test_plain_json():
    assert extract_json('{"a": 1}') == {"a": 1}


def test_markdown_fenced_json():
    assert extract_json("prose\n```json\n{\"a\": 1}\n```\ntrailing") == {"a": 1}


def test_fence_without_language():
    assert extract_json("```\n{\"a\": 2}\n```") == {"a": 2}


def test_prose_then_object():
    assert extract_json('Here you go: {"a": 3} thanks') == {"a": 3}


def test_array_payload():
    assert extract_json('[1, 2, 3]') == [1, 2, 3]


def test_truncated_object_recovered():
    # Simulates a token-limit cutoff mid-object.
    assert extract_json('{"a": 1, "b": [1, 2') == {"a": 1, "b": [1, 2]}


def test_truncated_midstring_gives_up_gracefully():
    # Unclosed string is unrecoverable -> None, never crashes.
    assert extract_json('{"a": "unterminated') is None


def test_garbage_returns_none():
    assert extract_json("not json at all") is None


def test_empty_returns_none():
    assert extract_json("") is None
    assert extract_json("   ") is None


def test_strip_code_fences_passthrough():
    assert strip_code_fences("no fences here") == "no fences here"
