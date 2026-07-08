"""AltTextGenerationService implementations (Milestone 1).

This module holds the concrete :class:`core.interfaces.AltTextGenerationService`
implementations — the AI layer that proposes *real*, accessible alt text for an
image, replacing the Milestone 0 filename heuristic:

* :class:`LlmAltTextGenerationService` — backed by an injected
  :class:`core.interfaces.LLMClient`. It builds an accessibility-first prompt
  from the page/image context, asks the model for a concise description, cleans
  the result, and returns it with the model's identity for provenance. Every
  handled failure (provider unavailable/timeout, empty or unusable output) is
  returned as a typed :class:`~core.results.Err` carrying a
  :class:`~core.exceptions.GenerationError`; it never raises for a handled
  failure, so the Fix_Generator can degrade gracefully.
* :class:`DeterministicAltTextGenerationService` — a network-free, deterministic
  double implementing the same contract, for unit tests and offline/opt-out
  environments. Given the same input it always returns the same output.

Responsibility boundary (strict): this layer only *proposes* content. It never
writes to the Digital_Twin and never publishes to the live site — those are the
Fix_Generator/Digital_Twin and the Publishing_Adapter's jobs respectively.

Per the workspace dependency rule, this subsystem depends only on Core_Package.
"""

from __future__ import annotations

import os
import re
from urllib.parse import urlsplit

from core.exceptions import AiGeneratorError, GenerationError
from core.interfaces import LLMClient
from core.results import Err, Ok, Result
from core.types import AltTextGenerationInput, AltTextGenerationOutput

__all__ = [
    "LlmAltTextGenerationService",
    "DeterministicAltTextGenerationService",
    "build_alt_text_prompt",
    "ALT_TEXT_SYSTEM_PROMPT",
]

#: Steering instruction sent as the system message. Accessibility-first, concise,
#: and explicitly not keyword-stuffed; forbids the redundant "image of" /
#: "picture of" prefixes that screen readers already announce.
ALT_TEXT_SYSTEM_PROMPT = (
    "You write concise, descriptive alt text for images to improve web "
    "accessibility. Describe what the image shows in plain, human-useful "
    "language for a screen-reader user. Do not keyword-stuff. Do not begin with "
    "'image of', 'picture of', or 'photo of' — screen readers already announce "
    "that it is an image. Reply with only the alt text, no quotes and no "
    "surrounding commentary."
)

#: Redundant lead-ins to strip if the model produces them anyway.
_REDUNDANT_PREFIXES = (
    "image of ",
    "an image of ",
    "a image of ",
    "picture of ",
    "a picture of ",
    "photo of ",
    "a photo of ",
    "photograph of ",
    "a photograph of ",
    "graphic of ",
    "a graphic of ",
)

#: A non-empty fallback description used by the deterministic fake when no
#: readable words can be derived from the context.
_FALLBACK_DESCRIPTION = "Decorative image"


class LlmAltTextGenerationService:
    """An :class:`core.interfaces.AltTextGenerationService` backed by an LLM.

    Args:
        llm_client: The injected :class:`core.interfaces.LLMClient` seam.
        model: The model/version identifier recorded on the output for
            provenance (should match the model the client actually calls).
        max_output_tokens: Optional generation cap passed through to the client;
            alt text is short so a small value keeps latency/cost low.
    """

    def __init__(
        self,
        llm_client: LLMClient,
        *,
        model: str,
        max_output_tokens: int | None = None,
    ) -> None:
        self._llm = llm_client
        self._model = model
        self._max_output_tokens = max_output_tokens

    def generate_alt_text(
        self, request: AltTextGenerationInput
    ) -> Result[AltTextGenerationOutput, GenerationError]:
        """Propose alt text for ``request`` via the LLM (Milestone 1).

        Returns :class:`~core.results.Ok` with the cleaned description and the
        model identity, or :class:`~core.results.Err` with a
        :class:`~core.exceptions.GenerationError` when the model is unavailable,
        times out, or returns empty/unusable text. Never raises for a handled
        failure.
        """
        prompt = build_alt_text_prompt(request)
        try:
            raw = self._llm.complete(
                prompt,
                system=ALT_TEXT_SYSTEM_PROMPT,
                max_output_tokens=self._max_output_tokens,
            )
        except AiGeneratorError as exc:
            # Already a typed generation-layer failure (e.g. LLMUnavailableError).
            return Err(exc)
        except Exception as exc:  # noqa: BLE001 - wrap any provider error, typed
            return Err(
                GenerationError(
                    f"LLM alt-text generation failed ({type(exc).__name__})"
                )
            )

        alt_text = _clean_alt_text(raw)
        if not alt_text:
            return Err(
                GenerationError(
                    "LLM returned empty or unusable alt text after cleaning."
                )
            )
        # A plain text completion carries no calibrated confidence, so we report
        # None rather than inventing a number.
        return Ok(
            AltTextGenerationOutput(
                alt_text=alt_text, model=self._model, confidence=None
            )
        )


class DeterministicAltTextGenerationService:
    """A deterministic, network-free :class:`core.interfaces.AltTextGenerationService`.

    Produces stable, human-readable alt text derived from the image filename and
    page context, honoring ``request.max_length`` via word-boundary truncation so
    its output always respects the requested budget. It never contacts a model,
    so it is a safe default for offline/opt-out environments and a simple,
    repeatable double for unit tests.

    Args:
        model: The model identity to stamp on the output for provenance.
        confidence: The self-reported confidence to return (default ``0.9``).
    """

    def __init__(
        self,
        *,
        model: str = "deterministic-alttext-v1",
        confidence: float | None = 0.9,
    ) -> None:
        self._model = model
        self._confidence = confidence

    def generate_alt_text(
        self, request: AltTextGenerationInput
    ) -> Result[AltTextGenerationOutput, GenerationError]:
        """Return deterministic alt text derived from ``request`` (never fails)."""
        description = _derive_description(request)
        if request.max_length is not None:
            description = _truncate_on_word_boundary(description, request.max_length)
        if not description:
            description = _FALLBACK_DESCRIPTION
        return Ok(
            AltTextGenerationOutput(
                alt_text=description,
                model=self._model,
                confidence=self._confidence,
            )
        )


# --- Prompt construction ------------------------------------------------------


def build_alt_text_prompt(request: AltTextGenerationInput) -> str:
    """Build the user prompt for alt-text generation from ``request``.

    Includes whatever context the crawler captured — page title, nearby text,
    the image URL/filename, and any existing alt text — and states the length
    budget. The service must work with degraded context, so any missing field is
    simply omitted rather than blocking generation.
    """
    lines: list[str] = ["Write alt text for an image on a web page."]

    filename = _filename_from_url(request.image_url)
    if filename:
        lines.append(f"Image filename: {filename}")
    if request.image_url:
        lines.append(f"Image URL: {request.image_url}")
    if request.page_title:
        lines.append(f"Page title: {request.page_title}")
    if request.surrounding_text:
        # Bound the context so a huge page body cannot balloon the prompt.
        context = request.surrounding_text.strip()
        if len(context) > 500:
            context = context[:500].rstrip() + "…"
        lines.append(f"Surrounding text: {context}")
    if request.existing_alt_text and request.existing_alt_text.strip():
        lines.append(
            f"Existing alt text to improve: {request.existing_alt_text.strip()}"
        )

    budget = request.max_length if request.max_length is not None else 125
    lines.append(
        f"Keep it under {budget} characters, concise and descriptive. "
        "Reply with only the alt text."
    )
    return "\n".join(lines)


# --- Text helpers -------------------------------------------------------------


def _clean_alt_text(text: str) -> str:
    """Normalize raw model output into usable alt text.

    Trims whitespace, removes wrapping quotes, drops a trailing period, and
    strips redundant "image of"/"picture of"-style lead-ins the system prompt
    already forbids (defensive — models sometimes add them anyway).
    """
    if not text:
        return ""
    cleaned = text.strip()

    # Strip a single pair of wrapping quotes if present.
    if len(cleaned) >= 2 and cleaned[0] in "\"'" and cleaned[-1] == cleaned[0]:
        cleaned = cleaned[1:-1].strip()

    # Collapse internal whitespace/newlines to single spaces.
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    # Drop a redundant lead-in prefix (case-insensitive), once.
    lowered = cleaned.lower()
    for prefix in _REDUNDANT_PREFIXES:
        if lowered.startswith(prefix):
            cleaned = cleaned[len(prefix):].strip()
            break

    # Drop a single trailing period for a cleaner attribute value.
    if cleaned.endswith(".") and not cleaned.endswith(".."):
        cleaned = cleaned[:-1].strip()

    # Capitalize the first character for readability without altering the rest.
    if cleaned:
        cleaned = cleaned[0].upper() + cleaned[1:]
    return cleaned


def _derive_description(request: AltTextGenerationInput) -> str:
    """Derive a deterministic, readable description from the request context."""
    filename = _filename_from_url(request.image_url)
    words = _words_from_filename(filename)
    if words:
        base = words
    elif request.page_title and request.page_title.strip():
        base = request.page_title.strip()
    else:
        base = _FALLBACK_DESCRIPTION
    return _clean_alt_text(base)


def _words_from_filename(filename: str) -> str:
    """Turn an image filename into readable, space-separated words."""
    name = (filename or "").strip()
    name = name.replace("\\", "/").split("/")[-1]
    name = name.split("?", 1)[0].split("#", 1)[0]
    stem, _ext = os.path.splitext(name)
    if stem:
        name = stem
    text = name.replace("%20", " ")
    text = re.sub(r"[-_.+]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _filename_from_url(url: str) -> str:
    """Return the trailing filename component of a URL or path."""
    if not url:
        return ""
    path = urlsplit(url).path or url
    return path.rsplit("/", 1)[-1] if path else ""


def _truncate_on_word_boundary(text: str, max_length: int) -> str:
    """Truncate ``text`` to at most ``max_length`` chars on a word boundary.

    Never splits a word mid-token: if a single word already exceeds the budget it
    is hard-cut as a last resort, otherwise the text is cut back to the last
    whole word that fits.
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
    # A single over-long word: hard-cut as the only option.
    return window.rstrip()
