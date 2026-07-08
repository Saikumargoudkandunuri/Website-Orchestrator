"""Unit tests for :class:`LlmAltTextGenerationService` (Milestone 1).

Drive the LLM-backed service through the injected :class:`LLMClient` seam so no
network is touched. These cover the happy path (cleaned text + model provenance),
the prompt actually carrying the page/image context, defensive cleaning of a
model that ignores instructions, and every handled-failure path returning a typed
:class:`~core.results.Err` rather than raising.
"""

from __future__ import annotations

from ai_generator import LlmAltTextGenerationService, StaticLLMClient
from ai_generator.service import ALT_TEXT_SYSTEM_PROMPT, build_alt_text_prompt
from core.exceptions import GenerationError, LLMUnavailableError
from core.results import Err, Ok
from core.types import AltTextGenerationInput


def _req(**kw: object) -> AltTextGenerationInput:
    base: dict[str, object] = {"page_url": "https://x/p", "image_url": "https://x/hero.jpg"}
    base.update(kw)
    return AltTextGenerationInput(**base)  # type: ignore[arg-type]


class RaisingLLMClient:
    """An LLMClient that raises the given exception when called."""

    def __init__(self, exc: Exception) -> None:
        self._exc = exc

    def complete(self, prompt: str, *, system=None, max_output_tokens=None) -> str:
        raise self._exc


def test_happy_path_returns_cleaned_text_and_model() -> None:
    svc = LlmAltTextGenerationService(
        StaticLLMClient("A cyclist on a mountain trail"), model="test-model-1"
    )
    result = svc.generate_alt_text(_req())
    assert isinstance(result, Ok)
    out = result.unwrap()
    assert out.alt_text == "A cyclist on a mountain trail"
    assert out.model == "test-model-1"
    # A plain completion carries no calibrated confidence.
    assert out.confidence is None


def test_prompt_carries_page_and_image_context() -> None:
    client = StaticLLMClient("desc", echo_prompt=False)
    svc = LlmAltTextGenerationService(client, model="m")
    svc.generate_alt_text(
        _req(
            image_url="https://x/uploads/sunset.jpg",
            page_title="Beach holidays",
            surrounding_text="Watch the sun set over the bay.",
            max_length=125,
        )
    )
    # The client recorded exactly one call; the system prompt and user prompt
    # both flowed through with the context embedded.
    assert len(client.calls) == 1
    prompt, system, _tokens = client.calls[0]
    assert system == ALT_TEXT_SYSTEM_PROMPT
    assert "sunset.jpg" in prompt
    assert "Beach holidays" in prompt
    assert "Watch the sun set" in prompt
    assert "125" in prompt


def test_strips_redundant_prefix_and_quotes() -> None:
    svc = LlmAltTextGenerationService(
        StaticLLMClient('"Image of a red bicycle."'), model="m"
    )
    out = svc.generate_alt_text(_req()).unwrap()
    # Wrapping quotes, the redundant "image of" lead-in, and trailing period are
    # all removed; the first letter is capitalized.
    assert out.alt_text == "A red bicycle"


def test_empty_completion_is_a_typed_error() -> None:
    svc = LlmAltTextGenerationService(StaticLLMClient("   "), model="m")
    result = svc.generate_alt_text(_req())
    assert isinstance(result, Err)
    assert isinstance(result.unwrap_err(), GenerationError)


def test_llm_unavailable_is_returned_as_err_not_raised() -> None:
    svc = LlmAltTextGenerationService(
        RaisingLLMClient(LLMUnavailableError("provider down")), model="m"
    )
    result = svc.generate_alt_text(_req())
    assert isinstance(result, Err)
    # The typed generation-layer error is preserved.
    assert isinstance(result.unwrap_err(), LLMUnavailableError)


def test_unexpected_exception_is_wrapped_as_generation_error() -> None:
    svc = LlmAltTextGenerationService(
        RaisingLLMClient(RuntimeError("kaboom")), model="m"
    )
    result = svc.generate_alt_text(_req())
    assert isinstance(result, Err)
    err = result.unwrap_err()
    assert isinstance(err, GenerationError)
    # The raw error text is not leaked; only the type name is summarized.
    assert "kaboom" not in str(err)
    assert "RuntimeError" in str(err)


def test_build_prompt_degrades_gracefully_with_missing_context() -> None:
    # No title, no surrounding text, no existing alt — must still produce a prompt.
    prompt = build_alt_text_prompt(_req(page_title=None, surrounding_text=None))
    assert "alt text" in prompt.lower()
    assert "hero.jpg" in prompt
