"""Milestone 1 — FixGenerator with an injected AltTextGenerationService.

These unit tests cover the AI-backed ``missing_alt_text`` path added in Milestone
1, driving :meth:`fix_generator.FixGenerator.generate_fix` with an injected
:class:`~core.interfaces.AltTextGenerationService`. The bare ``FixGenerator()``
(no service) keeps the Milestone 0 filename-heuristic behavior, which is proven
by the existing Milestone 0 properties; here we exercise the new behavior:

* a resolvable image yields an auto-applicable ``update_alt_text`` fix carrying
  the AI suggestion and its model/confidence provenance;
* an unresolvable image still yields a fix carrying the AI suggestion + provenance
  but report-only (no write target);
* a generation failure degrades gracefully to a report-only fix (no crash);
* a proposal equal to the existing alt text is a no-op (``None``);
* an over-length proposal is retried and, failing that, truncated on a word
  boundary — never mid-word;
* only ``missing_alt_text`` uses the service; other issue types are unaffected;
* the transform still does not mutate its inputs.
"""

from __future__ import annotations

from datetime import datetime, timezone

from ai_generator import DeterministicAltTextGenerationService
from core.constants import MAX_ALT_TEXT_LEN
from core.exceptions import GenerationError
from core.results import Err, Ok, Result
from core.types import (
    AltTextGenerationInput,
    AltTextGenerationOutput,
    CrawledPage,
    FixStatus,
    FixType,
    ImageRef,
    Issue,
    IssueDetail,
    IssueType,
    Severity,
)
from fix_generator import FixGenerator

NOW = datetime(2024, 1, 1, tzinfo=timezone.utc)
TENANT = "tenant-a"


# --- Fakes --------------------------------------------------------------------


class ConstantService:
    """Returns a fixed :class:`AltTextGenerationOutput` (ignores max_length)."""

    def __init__(self, alt_text: str, *, model: str = "svc-1", confidence=0.75) -> None:
        self._out = AltTextGenerationOutput(
            alt_text=alt_text, model=model, confidence=confidence
        )
        self.call_count = 0

    def generate_alt_text(self, request: AltTextGenerationInput):
        self.call_count += 1
        return Ok(self._out)


class FailingService:
    """Always returns a typed generation failure."""

    def generate_alt_text(
        self, request: AltTextGenerationInput
    ) -> Result[AltTextGenerationOutput, GenerationError]:
        return Err(GenerationError("model unavailable"))


# --- Builders -----------------------------------------------------------------


def _issue(issue_type: IssueType = IssueType.MISSING_ALT_TEXT) -> Issue:
    return Issue(
        id="issue-1",
        tenant_id=TENANT,
        issue_type=issue_type,
        severity=Severity.LOW,
        description="an issue",
        detail=IssueDetail(page_url="https://example.com/", element="img"),
        ignored=False,
    )


def _page(images: list[ImageRef]) -> CrawledPage:
    return CrawledPage(
        url="https://example.com/",
        final_url="https://example.com/",
        status_code=200,
        title="Bikes for sale",
        images=images,
        crawled_at=NOW,
    )


# --- Tests --------------------------------------------------------------------


def test_resolvable_image_yields_ai_auto_applicable_fix() -> None:
    gen = FixGenerator(ConstantService("A red touring bicycle"))
    fix = gen.generate_fix(
        _issue(), _page([ImageRef(media_id=42, filename="bike.jpg", alt_text=None)])
    )
    assert fix is not None
    assert fix.auto_applicable == 1
    assert fix.fix_type is FixType.UPDATE_ALT_TEXT
    assert fix.target_ref is not None and fix.target_ref.media_id == 42
    assert fix.proposed_value == "A red touring bicycle"
    assert fix.generation_model == "svc-1"
    assert fix.generation_confidence == 0.75
    assert fix.status is FixStatus.PENDING
    # Provenance is recorded; it is NOT labeled a filename heuristic.
    assert "ai model" in fix.reason.lower()
    assert "heuristic" not in fix.reason.lower()


def test_unresolvable_image_yields_report_only_fix_with_suggestion() -> None:
    gen = FixGenerator(ConstantService("A team photo"))
    fix = gen.generate_fix(
        _issue(), _page([ImageRef(media_id=None, filename="team.jpg", alt_text=None)])
    )
    assert fix is not None
    # Report-only (no resolvable media target) but still carries the AI suggestion.
    assert fix.auto_applicable == 0
    assert fix.target_ref is None
    assert fix.proposed_value == "A team photo"
    assert fix.generation_model == "svc-1"
    assert "report-only" in fix.reason.lower()


def test_generation_failure_degrades_to_report_only() -> None:
    gen = FixGenerator(FailingService())
    fix = gen.generate_fix(
        _issue(), _page([ImageRef(media_id=42, filename="bike.jpg", alt_text=None)])
    )
    assert fix is not None
    assert fix.auto_applicable == 0
    assert fix.fix_type is None
    assert fix.proposed_value is None
    assert fix.reason.startswith("AI alt-text generation failed:")
    assert fix.generation_model is None


def test_noop_when_proposal_equals_existing_alt_text() -> None:
    gen = FixGenerator(ConstantService("Already described"))
    fix = gen.generate_fix(
        _issue(),
        _page([ImageRef(media_id=42, filename="bike.jpg", alt_text="Already described")]),
    )
    assert fix is None


def test_overlength_proposal_is_retried_then_word_boundary_truncated() -> None:
    long_text = " ".join(["word"] * 60)  # far over 125 chars
    service = ConstantService(long_text)  # ignores max_length, so retry can't help
    gen = FixGenerator(service)
    fix = gen.generate_fix(
        _issue(), _page([ImageRef(media_id=42, filename="bike.jpg", alt_text=None)])
    )
    assert fix is not None
    assert fix.proposed_value is not None
    assert len(fix.proposed_value) <= MAX_ALT_TEXT_LEN
    # A truncation-aware retry was attempted before falling back to truncation.
    assert service.call_count >= 2
    # Never split a word mid-token.
    assert not fix.proposed_value.endswith("wor")
    assert all(w == "word" for w in fix.proposed_value.split())


def test_deterministic_service_produces_valid_within_limit() -> None:
    gen = FixGenerator(DeterministicAltTextGenerationService())
    fix = gen.generate_fix(
        _issue(),
        _page([ImageRef(media_id=7, filename="green-mountain-bike.jpg", alt_text=None)]),
    )
    assert fix is not None
    assert fix.auto_applicable == 1
    assert fix.proposed_value == "Green mountain bike"
    assert 0 < len(fix.proposed_value) <= MAX_ALT_TEXT_LEN
    assert fix.generation_model == "deterministic-alttext-v1"


def test_service_only_used_for_missing_alt_text() -> None:
    # A non-alt-text issue must not touch the AI service and stays report-only.
    service = ConstantService("should not be used")
    gen = FixGenerator(service)
    fix = gen.generate_fix(
        _issue(IssueType.MISSING_META_DESCRIPTION), _page([])
    )
    assert fix is not None
    assert service.call_count == 0
    assert fix.fix_type is None
    assert fix.auto_applicable == 0
    assert fix.generation_model is None


def test_ai_path_does_not_mutate_inputs() -> None:
    gen = FixGenerator(ConstantService("A bicycle"))
    issue = _issue()
    page = _page([ImageRef(media_id=42, filename="bike.jpg", alt_text=None)])
    issue_before = issue.model_dump()
    page_before = page.model_dump()
    gen.generate_fix(issue, page)
    assert issue.model_dump() == issue_before
    assert page.model_dump() == page_before
