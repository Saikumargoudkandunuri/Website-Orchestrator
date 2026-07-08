"""Validation pipeline — composes validators per capability (§7).

Nothing an :class:`AIProvider` produces is trusted until it passes through here.
The pipeline:

1. parses the raw AI text into JSON (tolerant of markdown fences / truncation);
2. runs the capability's declared JSON schema validator;
3. runs the capability-specific validators (hallucination guard, HTML sanitizer,
   schema.org, slug, keyword sanity, external-link, OG image), in order;
4. aggregates them into a :class:`ValidationResult` whose ``status`` is
   ``passed`` | ``corrected`` | ``failed`` — the value recorded on
   ``AIInvocation.validation_result``.

A validator may *correct* the payload in place (sanitized HTML, downgraded URL);
a single hard failure makes the whole result ``failed`` so the orchestrator
retries (bounded) before falling back to leaving the field null — never
persisting invalid data. It also exposes immutability enforcement (§4.12).
"""

from __future__ import annotations

from typing import Any, Protocol

from core.logging import get_logger
from intelligence.ai.parsing import extract_json
from intelligence.field_paths import path_matches_any
from intelligence.models.ai_invocation import ValidationOutcome
from intelligence.validation.context import ValidationContext
from intelligence.validation.external_link_validator import ExternalLinkValidator
from intelligence.validation.hallucination_guard import HallucinationGuard
from intelligence.validation.html_sanitizer import HtmlSanitizer
from intelligence.validation.json_schema_validator import JsonSchemaValidator
from intelligence.validation.keyword_sanity_validator import KeywordSanityValidator
from intelligence.validation.og_image_validator import OgImageValidator
from intelligence.validation.result import ValidationResult, ValidatorOutcome
from intelligence.validation.schema_org_validator import SchemaOrgValidator
from intelligence.validation.url_slug_validator import UrlSlugValidator

__all__ = ["Validator", "ValidationPipeline", "is_writable"]

_log = get_logger("intelligence.validation")


class Validator(Protocol):
    def validate(
        self, payload: Any, *, context: ValidationContext | None = None
    ) -> ValidatorOutcome: ...


#: Per-capability extra validators (beyond the always-run JSON schema check).
#: Built lazily per pipeline instance so validators stay stateless singletons.
def _capability_validators() -> dict[str, list[Validator]]:
    return {
        "keyword_analysis": [KeywordSanityValidator()],
        "content_analysis": [],
        "meta_generator": [HallucinationGuard(["meta_description"], factual=True)],
        "title_generator": [],
        "slug_generator": [UrlSlugValidator("slug")],
        "schema_generator": [SchemaOrgValidator("jsonld")],
        "image_alt": [],
        "internal_linking": [ExternalLinkValidator()],
        "seo_audit": [],
        "technical_audit": [],
        "accessibility": [],
        "faq_generator": [HtmlSanitizer(), HallucinationGuard([], factual=True)],
        "content_rewrite": [HtmlSanitizer(["rewritten"])],
        "content_expansion": [HtmlSanitizer(["expansion"])],
        "og_image": [OgImageValidator()],
    }


class ValidationPipeline:
    """Composes and runs the validator chain for a capability."""

    def __init__(self) -> None:
        self._by_capability = _capability_validators()

    def validate(
        self,
        capability: str,
        raw_text: str,
        schema: dict[str, Any],
        *,
        context: ValidationContext | None = None,
    ) -> ValidationResult:
        ctx = context or ValidationContext(capability=capability)

        payload = extract_json(raw_text)
        if payload is None:
            return ValidationResult(
                status=ValidationOutcome.FAILED,
                errors=["AI output was not parseable JSON"],
            )

        errors: list[str] = []
        warnings: list[str] = []
        corrected = False

        chain: list[Validator] = [JsonSchemaValidator(schema)]
        chain.extend(self._by_capability.get(capability, []))

        for validator in chain:
            outcome = validator.validate(payload, context=ctx)
            payload = outcome.payload if outcome.payload is not None else payload
            warnings.extend(outcome.warnings)
            if outcome.corrected:
                corrected = True
            if not outcome.ok:
                errors.extend(outcome.errors)
                # Stop at the first hard failure; the orchestrator will retry.
                return ValidationResult(
                    status=ValidationOutcome.FAILED,
                    errors=errors,
                    warnings=warnings,
                    payload=payload,
                )

        status = ValidationOutcome.CORRECTED if corrected else ValidationOutcome.PASSED
        return ValidationResult(
            status=status, errors=errors, warnings=warnings, payload=payload
        )


def is_writable(path: str, immutable_fields: list[str]) -> bool:
    """Return ``False`` (and log) when ``path`` is locked by ``immutable_fields``.

    Enforces the §4.12 immutability rule at the validation layer: a proposal
    targeting a locked field path is rejected (logged, not crashed).
    """
    if path_matches_any(path, immutable_fields):
        _log.warning(
            "immutable_field_write_rejected",
            field_path=path,
        )
        return False
    return True
