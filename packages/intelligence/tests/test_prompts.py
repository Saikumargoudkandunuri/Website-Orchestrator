"""Prompt template tests (§9): build() well-formed + response_schema valid JSON schema."""

from __future__ import annotations

import pytest

from intelligence.ai.prompt_registry import default_prompt_registry
from intelligence.prompts import ALL_PROMPT_TEMPLATES, PromptContext

REGISTRY = default_prompt_registry()

_RICH = PromptContext(
    page_url="https://x/p", page_type="service", language="en",
    title="Title", meta_description="desc", slug="p",
    headings=["H1 text"], first_paragraph="First para.", content_excerpt="Body text.",
    word_count=200, primary_focus_keyphrase="kp", secondary_keyphrases=["a", "b"],
    top_keywords=["kp", "widgets"],
    images=[{"element_id": "i1", "filename": "a.jpg", "alt": None}],
    known_internal_urls=["/about"],
)
_EMPTY = PromptContext(page_url="")
_SHORT = PromptContext(page_url="https://x/p", title="T", word_count=1)
_NON_EN = PromptContext(page_url="https://x/p", language="hi", title="मॉड्यूलर किचन", word_count=50)


def test_registry_has_all_fourteen():
    # Milestone 2 added 14 prompts; Milestone 3 added 5 more = 19 total.
    assert len(REGISTRY.capabilities()) == 19
    assert len(ALL_PROMPT_TEMPLATES) == 19


@pytest.mark.parametrize("capability", default_prompt_registry().capabilities())
@pytest.mark.parametrize("ctx", [_RICH, _EMPTY, _SHORT, _NON_EN])
def test_build_produces_well_formed_request(capability, ctx):
    template = REGISTRY.get(capability)
    request = template.build(ctx)
    assert request.prompt and isinstance(request.prompt, str)
    assert request.metadata["capability"] == capability
    assert request.metadata["prompt_version"] == template.version


@pytest.mark.parametrize("capability", default_prompt_registry().capabilities())
def test_response_schema_is_valid_json_schema(capability):
    schema = REGISTRY.get(capability).response_schema()
    assert isinstance(schema, dict)
    assert schema.get("type") == "object"
    assert isinstance(schema.get("properties", {}), dict)


def test_versions_present():
    for cls in ALL_PROMPT_TEMPLATES:
        t = cls()
        assert t.capability and t.version
