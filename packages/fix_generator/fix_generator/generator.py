"""Fix_Generator — the pure transformation from an :class:`Issue` to at most one
:class:`SuggestedFix` (Requirement 5).

``generate_fix`` is a *pure* transform: given an :class:`Issue` and the
:class:`CrawledPage` it was raised against, it returns exactly one
:class:`SuggestedFix` or ``None`` and **never writes to the database** (Req 5.1).
It maps issue types to fixes as follows:

* Ignored issue, or an issue type with no defined fix mapping → ``None``
  (Req 5.2).
* ``missing_alt_text`` with a resolvable media identifier and a non-empty image
  filename → an auto-applicable ``SuggestedFix`` (``auto_applicable=1``,
  ``fix_type=update_alt_text``) carrying non-empty heuristic alt text of at most
  :data:`~core.constants.MAX_ALT_TEXT_LEN` characters derived from the filename.
  The alt text is explicitly labeled a *placeholder heuristic*, never
  represented as AI-generated content (Req 5.3, 5.4).
* ``missing_alt_text`` with no resolvable media identifier → a report-only
  ``SuggestedFix`` (``auto_applicable=0``) whose reason records that the media
  identifier could not be resolved, retaining the originating Issue reference
  (Req 5.5).
* Any other recognized issue type → a report-only ``SuggestedFix``
  (``auto_applicable=0``) recording a human-readable report-only reason
  (Req 5.6).

A broken-link issue never yields a generated replacement URL — its
``proposed_value`` is left empty (Req 5.7).

Per Requirement 15, this subsystem imports nothing internal to the orchestrator
beyond ``Core_Package``.
"""

from __future__ import annotations

import os
import re
import uuid

from core.constants import MAX_ALT_TEXT_LEN
from core.exceptions import GenerationError
from core.interfaces import AltTextGenerationService
from core.results import Err, Ok, Result, is_err, is_ok
from core.types import (
    AltTextGenerationInput,
    AltTextGenerationOutput,
    CrawledPage,
    FixStatus,
    FixType,
    ImageRef,
    Issue,
    IssueType,
    SuggestedFix,
    TargetRef,
)

__all__ = ["FixGenerator"]


#: Issue types the Fix_Generator recognizes and therefore maps to a
#: ``SuggestedFix``. ``missing_alt_text`` is the only auto-applicable type; every
#: other recognized type yields a report-only fix (Req 5.6). An issue type absent
#: from this set has no defined fix mapping and yields ``None`` (Req 5.2).
_RECOGNIZED_ISSUE_TYPES: frozenset[IssueType] = frozenset(IssueType)

#: A fallback alt text used only when a filename yields no readable words, so the
#: produced alt text is always non-empty (Req 5.3).
_FALLBACK_ALT_TEXT = "Image"

#: Label recorded on the auto-applicable fix so downstream reviewers know the alt
#: text is a filename-derived placeholder heuristic and NOT AI-generated content
#: (Req 5.4).
_HEURISTIC_LABEL = (
    "Placeholder alt text derived from the image filename as a heuristic "
    "(not AI-generated); review before approving."
)


class FixGenerator:
    """Pure transformation turning an :class:`Issue` into at most one
    :class:`SuggestedFix` (implements :class:`~core.interfaces.FixGeneratorPort`).

    ``generate_fix`` reads only its arguments and returns a value; it never
    writes to the database (Req 5.1). The optional injected
    :class:`~core.interfaces.AltTextGenerationService` is the only collaborator,
    and it too only *proposes* content, so the transform remains free of any
    persistence or publishing side effect.

    Alt-text generation strategy (Milestone 1)
    ------------------------------------------
    * **No service injected** (``alt_text_service is None``) — the default and
      the exact Milestone 0 behavior: a ``missing_alt_text`` issue with a
      resolvable media id yields an auto-applicable fix carrying a
      *filename-derived placeholder heuristic* (never represented as
      AI-generated), and an unresolvable one yields a report-only fix (Req 5.3-5.5).
    * **Service injected** — the ``missing_alt_text`` branch asks the service for
      *real* AI-generated alt text, records the model/confidence provenance on the
      fix, and validates it (non-empty, ≤ :data:`~core.constants.MAX_ALT_TEXT_LEN`
      with a truncation-aware retry, no-op skip when unchanged). If generation
      fails the branch degrades gracefully to a report-only fix recording the
      reason, so an AI outage never crashes the crawl workflow.

    A single :class:`FixGenerator` may be shared across issues and threads when
    its injected service (if any) is itself safe to share.
    """

    def __init__(
        self, alt_text_service: AltTextGenerationService | None = None
    ) -> None:
        """Build a Fix_Generator.

        Args:
            alt_text_service: Optional AI alt-text generator. When ``None`` the
                generator uses the deterministic filename heuristic (Milestone 0
                behavior); when supplied, ``missing_alt_text`` fixes carry
                real AI-generated alt text with graceful degradation on failure.
        """
        self._alt_text_service = alt_text_service

    def generate_fix(
        self, issue: Issue, page: CrawledPage
    ) -> SuggestedFix | None:
        """Return exactly one :class:`SuggestedFix` for ``issue`` given ``page``,
        or ``None`` when no fix maps to the issue. Never writes to the database
        (Req 5.1, 5.2)."""

        # Req 5.2 — ignored issues, and issue types with no defined fix mapping,
        # yield no fix.
        if issue.ignored:
            return None
        if issue.issue_type not in _RECOGNIZED_ISSUE_TYPES:
            return None

        if issue.issue_type is IssueType.MISSING_ALT_TEXT:
            return self._alt_text_fix(issue, page)

        # Req 5.6 — every other recognized type is report-only. Broken-link
        # issues fall here and never receive a generated replacement URL
        # (proposed_value stays None), satisfying Req 5.7.
        return self._report_only_fix(
            issue,
            reason=(
                f"The '{issue.issue_type.value}' issue is report-only in "
                "Milestone 0; no automated fix is generated. Manual review "
                "and remediation are required."
            ),
        )

    # --- Branch builders ------------------------------------------------------

    def _alt_text_fix(
        self, issue: Issue, page: CrawledPage
    ) -> SuggestedFix | None:
        """Build the fix for a ``missing_alt_text`` issue.

        Dispatches to the AI-backed path when an
        :class:`~core.interfaces.AltTextGenerationService` is injected, and to
        the Milestone 0 filename heuristic otherwise (Req 5.3-5.5).
        """
        if self._alt_text_service is not None:
            return self._ai_alt_text_fix(issue, page, self._alt_text_service)
        return self._heuristic_alt_text_fix(issue, page)

    def _heuristic_alt_text_fix(
        self, issue: Issue, page: CrawledPage
    ) -> SuggestedFix:
        """Build a ``missing_alt_text`` fix from the filename heuristic (Req 5.3-5.5).

        This is the Milestone 0 behavior, unchanged: it runs when no AI
        generation service is injected.
        """

        image = _resolve_image(issue, page)

        # Req 5.5 — no resolvable media identifier (or no matching image with a
        # usable filename): produce a report-only fix that explains why and
        # retains the originating Issue reference (issue_id).
        if image is None or image.media_id is None or _is_blank(image.filename):
            return self._report_only_fix(
                issue,
                reason=(
                    "Could not resolve a WordPress media identifier for the "
                    "image missing alt text, so alt text cannot be "
                    "auto-applied; manual review is required."
                ),
            )

        # Req 5.3 / 5.4 — resolvable: auto-applicable alt-text write with a
        # non-empty, filename-derived heuristic value (<= MAX_ALT_TEXT_LEN),
        # explicitly labeled a placeholder heuristic (not AI-generated).
        return SuggestedFix(
            id=_new_fix_id(),
            tenant_id=issue.tenant_id,
            issue_id=issue.id,
            fix_type=FixType.UPDATE_ALT_TEXT,
            auto_applicable=1,
            target_ref=TargetRef(media_id=image.media_id),
            proposed_value=_derive_alt_text(image.filename),
            reason=_HEURISTIC_LABEL,
            status=FixStatus.PENDING,
        )

    def _ai_alt_text_fix(
        self,
        issue: Issue,
        page: CrawledPage,
        service: AltTextGenerationService,
    ) -> SuggestedFix | None:
        """Build a ``missing_alt_text`` fix from real AI-generated alt text (M1).

        Resolves the triggering image, asks the injected service for alt text,
        validates it against the Milestone 1 business rules, and constructs a
        typed fix carrying the suggestion and its generation provenance:

        * An image whose WordPress ``media_id`` is resolvable yields an
          auto-applicable ``update_alt_text`` fix (Governance still gates the
          publish — there is no unattended path).
        * An image with no resolvable ``media_id`` still yields a fix carrying the
          AI suggestion and provenance, but report-only (``auto_applicable=0``,
          no write target) until the media id is known.
        * A generation failure degrades gracefully to a report-only fix recording
          the reason — the crawl workflow never crashes (edge cases §5).
        * A proposal identical to the existing alt text is a no-op and yields
          ``None`` (no pointless fix, Req-style §3.6).
        """
        image = _resolve_image(issue, page)
        if image is None or _is_blank(image.filename):
            # No specific image to describe — nothing for the model to work with.
            return self._report_only_fix(
                issue,
                reason=(
                    "Could not resolve the image missing alt text on the page, "
                    "so no alt text could be generated; manual review is "
                    "required."
                ),
            )

        generation = self._generate_alt_text(service, issue, page, image)
        if is_err(generation):
            # Graceful degradation: record why and fall back to report-only so a
            # single failed generation never fails the whole crawl.
            return self._report_only_fix(
                issue,
                reason=f"AI alt-text generation failed: {generation.unwrap_err()}",
            )

        output = generation.unwrap()
        alt_text = (output.alt_text or "").strip()
        if not alt_text:
            return self._report_only_fix(
                issue,
                reason="AI alt-text generation returned empty text; manual review is required.",
            )

        # No-op skip: never create a fix that proposes the current value.
        existing = (image.alt_text or "").strip()
        if existing and alt_text == existing:
            return None

        resolvable = image.media_id is not None
        return SuggestedFix(
            id=_new_fix_id(),
            tenant_id=issue.tenant_id,
            issue_id=issue.id,
            fix_type=FixType.UPDATE_ALT_TEXT,
            auto_applicable=1 if resolvable else 0,
            target_ref=TargetRef(media_id=image.media_id) if resolvable else None,
            proposed_value=alt_text,
            reason=_ai_reason(output, resolvable=resolvable),
            status=FixStatus.PENDING,
            generation_model=output.model,
            generation_confidence=output.confidence,
        )

    def _generate_alt_text(
        self,
        service: AltTextGenerationService,
        issue: Issue,
        page: CrawledPage,
        image: ImageRef,
    ) -> Result[AltTextGenerationOutput, GenerationError]:
        """Call the service and enforce the length rule with a truncation-aware retry.

        Requests alt text within :data:`~core.constants.MAX_ALT_TEXT_LEN`. If the
        model overshoots, retries once with a tighter budget; if it still
        overshoots, truncates on a word boundary (never mid-word) as a last
        resort. Any raised error is wrapped into a typed
        :class:`~core.exceptions.GenerationError` so the caller can degrade
        gracefully.
        """
        request = AltTextGenerationInput(
            page_url=page.url,
            page_title=page.title,
            surrounding_text=None,  # not captured by the M0 crawler; degrade gracefully
            image_url=image.filename,
            existing_alt_text=image.alt_text,
            max_length=MAX_ALT_TEXT_LEN,
        )

        outcome = _safe_generate(service, request)
        if is_err(outcome):
            return outcome

        output = outcome.unwrap()
        if len((output.alt_text or "").strip()) <= MAX_ALT_TEXT_LEN:
            return outcome

        # Truncation-aware retry: ask again with a tighter budget rather than
        # silently hard-truncating mid-word.
        tighter = max(1, int(MAX_ALT_TEXT_LEN * 0.8))
        retry = _safe_generate(
            service, request.model_copy(update={"max_length": tighter})
        )
        if is_ok(retry):
            retry_out = retry.unwrap()
            retry_alt = (retry_out.alt_text or "").strip()
            if 0 < len(retry_alt) <= MAX_ALT_TEXT_LEN:
                return Ok(retry_out.model_copy(update={"alt_text": retry_alt}))
            if retry_alt:
                output = retry_out  # still too long, but usable text to truncate

        truncated = _truncate_on_word_boundary(
            (output.alt_text or "").strip(), MAX_ALT_TEXT_LEN
        )
        return Ok(output.model_copy(update={"alt_text": truncated}))

    def _report_only_fix(self, issue: Issue, reason: str) -> SuggestedFix:
        """Build a report-only fix that records ``reason`` and retains the
        Issue reference; it proposes no value and no write target (Req 5.5, 5.6,
        5.7)."""

        return SuggestedFix(
            id=_new_fix_id(),
            tenant_id=issue.tenant_id,
            issue_id=issue.id,
            fix_type=None,
            auto_applicable=0,
            target_ref=None,
            proposed_value=None,
            reason=reason,
            status=FixStatus.PENDING,
        )


# --- Module-level helpers -----------------------------------------------------


def _new_fix_id() -> str:
    """Return a fresh unique identifier for a SuggestedFix."""

    return str(uuid.uuid4())


def _is_blank(value: str | None) -> bool:
    """Return ``True`` when ``value`` is ``None`` or only whitespace."""

    return value is None or value.strip() == ""


def _safe_generate(
    service: AltTextGenerationService, request: AltTextGenerationInput
) -> Result[AltTextGenerationOutput, GenerationError]:
    """Call ``service.generate_alt_text`` without ever letting it crash the crawl.

    The service contract is to return a :class:`~core.results.Result`, but this
    wrapper is defensive: a service that raises, or returns something that is
    neither :class:`~core.results.Ok` nor :class:`~core.results.Err`, is coerced
    into a typed :class:`~core.exceptions.GenerationError` failure so the
    Fix_Generator can always degrade gracefully (edge cases §5, acceptance #9).
    """
    try:
        result = service.generate_alt_text(request)
    except Exception as exc:  # noqa: BLE001 - a misbehaving service must not crash the crawl
        return Err(
            GenerationError(f"AI alt-text service raised {type(exc).__name__}")
        )
    if is_ok(result) or is_err(result):
        return result
    return Err(GenerationError("AI alt-text service returned a non-Result value."))


def _ai_reason(output: AltTextGenerationOutput, *, resolvable: bool) -> str:
    """Human-readable provenance recorded on an AI-generated alt-text fix.

    Names the model and (when reported) its confidence so a reviewer can judge
    the suggestion, and — for an unresolvable media target — explains why the fix
    is report-only rather than auto-applicable.
    """
    confidence = (
        f", confidence {output.confidence:.2f}"
        if output.confidence is not None
        else ""
    )
    reason = (
        f"Alt text proposed by AI model {output.model!r}{confidence}; "
        "review before approving."
    )
    if not resolvable:
        reason += (
            " The WordPress media identifier could not be resolved, so this "
            "suggestion is report-only and cannot be auto-applied until the "
            "media id is known."
        )
    return reason


def _truncate_on_word_boundary(text: str, max_length: int) -> str:
    """Truncate ``text`` to at most ``max_length`` chars without splitting a word.

    Cuts back to the last whole word that fits; only a single word longer than
    the whole budget is hard-cut, as a last resort. Used when an AI proposal
    overshoots the alt-text length limit even after a truncation-aware retry, so
    the stored value never ends mid-word.
    """
    if max_length <= 0:
        return ""
    if len(text) <= max_length:
        return text
    window = text[:max_length]
    if " " in window:
        trimmed = window.rsplit(" ", 1)[0].rstrip()
        if trimmed:
            return trimmed
    return window.rstrip()


def _resolve_image(issue: Issue, page: CrawledPage) -> ImageRef | None:
    """Return the :class:`ImageRef` the ``missing_alt_text`` ``issue`` refers to.

    The Check_Engine records the triggering image in ``issue.detail.element``.
    We match generically (rather than coupling to that exact string form) by
    looking for the image's ``media_id`` token or its ``filename`` inside the
    element. When the element does not identify a specific image, we fall back
    to the first image on the page that is missing alt text, then to the first
    image, so a resolvable candidate is still found when one exists.
    """

    images = page.images or []
    if not images:
        return None

    element = ""
    if issue.detail is not None and issue.detail.element:
        element = issue.detail.element

    if element:
        # Prefer a media_id token match — the most specific, resolvable signal.
        for image in images:
            if image.media_id is not None and (
                f"media_id={image.media_id}" in element
                or f"media_id {image.media_id}" in element
            ):
                return image
        # Then match by filename appearing in the element.
        for image in images:
            if image.filename and image.filename in element:
                return image

    # Fall back to the first image that is actually missing alt text.
    for image in images:
        if _is_blank(image.alt_text):
            return image

    return images[0]


def _derive_alt_text(filename: str) -> str:
    """Derive readable, non-empty heuristic alt text from an image ``filename``.

    The transformation strips any path and query, drops the file extension, and
    turns separator characters (``-``, ``_``, ``.``, ``+``, ``%20``) into spaces,
    yielding human-readable words. The result is capitalized for readability,
    guaranteed non-empty, and truncated to at most
    :data:`~core.constants.MAX_ALT_TEXT_LEN` characters (Req 5.3, 5.4).
    """

    name = (filename or "").strip()

    # Reduce a full path or URL to its final component.
    name = name.replace("\\", "/").split("/")[-1]
    # Drop any query string / fragment that rode along with the filename.
    name = name.split("?", 1)[0].split("#", 1)[0]

    # Drop the file extension (only when it leaves a non-empty stem).
    stem, _ext = os.path.splitext(name)
    if stem:
        name = stem

    # Turn common separators (and percent-encoded spaces) into spaces.
    text = name.replace("%20", " ")
    text = re.sub(r"[-_.+]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    if not text:
        text = _FALLBACK_ALT_TEXT

    # Capitalize the first character for readability without altering the rest.
    text = text[0].upper() + text[1:]

    if len(text) > MAX_ALT_TEXT_LEN:
        text = text[:MAX_ALT_TEXT_LEN].rstrip()
        if not text:
            text = _FALLBACK_ALT_TEXT[:MAX_ALT_TEXT_LEN]

    return text
