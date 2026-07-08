"""Validator + pipeline tests (§7, §9), including immutability enforcement (§4.12)."""

from __future__ import annotations

import pytest

from intelligence.ai.prompt_registry import default_prompt_registry
from intelligence.ai.providers.fake_provider import DEFAULT_FAKE_RESPONSES
from intelligence.models.ai_invocation import ValidationOutcome
from intelligence.validation import (
    ExternalLinkValidator,
    HtmlSanitizer,
    KeywordSanityValidator,
    SchemaOrgValidator,
    UrlSlugValidator,
    ValidationContext,
    ValidationPipeline,
    is_valid_slug,
    is_writable,
    sanitize_html,
)

REGISTRY = default_prompt_registry()
PIPE = ValidationPipeline()


@pytest.mark.parametrize("capability,raw", list(DEFAULT_FAKE_RESPONSES.items()))
def test_every_fake_response_passes_its_pipeline(capability, raw):
    if not REGISTRY.has(capability):
        pytest.skip("capability has no prompt (auxiliary fake response)")
    schema = REGISTRY.get(capability).response_schema()
    ctx = ValidationContext(capability=capability, top_keywords=["modular", "kitchens", "hyderabad", "design"])
    result = PIPE.validate(capability, raw, schema, context=ctx)
    assert result.passed, (capability, result.errors)


def test_unparseable_json_fails():
    schema = REGISTRY.get("meta_generator").response_schema()
    assert PIPE.validate("meta_generator", "not json", schema).status == ValidationOutcome.FAILED


def test_schema_mismatch_fails():
    schema = REGISTRY.get("meta_generator").response_schema()
    assert PIPE.validate("meta_generator", '{"nope": 1}', schema).status == ValidationOutcome.FAILED


def test_html_sanitizer_corrects():
    schema = REGISTRY.get("content_rewrite").response_schema()
    r = PIPE.validate("content_rewrite", '{"rewritten": "Hi <script>x()</script> ok"}', schema)
    assert r.status == ValidationOutcome.CORRECTED
    assert "<script>" not in r.payload["rewritten"]


def test_sanitize_html_strips_event_handlers_and_js_uris():
    out, changed = sanitize_html('<a href="javascript:alert(1)" onclick="x()">t</a>')
    assert changed and "javascript:" not in out and "onclick" not in out


def test_external_link_downgrade():
    schema = REGISTRY.get("internal_linking").response_schema()
    raw = ('{"suggested_external_links": [{"anchor_text_context": "x", '
           '"suggested_target_url": "not a url", "suggested_target_description": "d", '
           '"reasoning": "r", "authority_rationale": "a"}]}')
    r = PIPE.validate("internal_linking", raw, schema)
    assert r.status == ValidationOutcome.CORRECTED
    assert r.payload["suggested_external_links"][0]["suggested_target_url"] is None


@pytest.mark.parametrize("n,ok", [(3, False), (4, True), (10, True), (11, False)])
def test_secondary_keyphrase_bounds(n, ok):
    schema = REGISTRY.get("keyword_analysis").response_schema()
    kps = ", ".join(f'"k{i}"' for i in range(n))
    raw = '{"primary_focus_keyphrase": "widgets", "secondary_keyphrases": [' + kps + "]}"
    r = PIPE.validate("keyword_analysis", raw, schema, context=ValidationContext(top_keywords=["widgets"]))
    assert r.passed == ok


def test_keyword_focus_mismatch_is_warning_not_failure():
    v = KeywordSanityValidator()
    out = v.validate(
        {"primary_focus_keyphrase": "unrelated term", "secondary_keyphrases": ["a", "b", "c", "d"]},
        context=ValidationContext(top_keywords=["kitchens", "design"]),
    )
    assert out.ok and out.warnings


def test_schema_org_rejects_invalid_jsonld():
    v = SchemaOrgValidator("jsonld")
    assert not v.validate({"jsonld": '{"foo": 1}'}).ok  # no @context/@type
    assert v.validate({"jsonld": '{"@context": "https://schema.org", "@type": "LocalBusiness"}'}).ok


def test_slug_validator():
    assert is_valid_slug("modular-kitchens-hyderabad")
    assert not is_valid_slug("Bad_Slug!")
    v = UrlSlugValidator()
    assert not v.validate({"slug": "taken"}, context=ValidationContext(existing_slugs={"taken"})).ok


# --- Immutability (§4.12, acceptance #6) --------------------------------------


def test_is_writable_blocks_locked_paths():
    locked = ["identity.canonical_url", "content_intelligence.first_paragraph"]
    assert is_writable("metadata.seo_title.proposed_value", locked)
    assert not is_writable("identity.canonical_url", locked)
    assert not is_writable("content_intelligence.first_paragraph.nested", locked)
