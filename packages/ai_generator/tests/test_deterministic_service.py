"""Unit tests for :class:`DeterministicAltTextGenerationService` (Milestone 1).

The deterministic service is the network-free double used to drive generator and
integration tests without an LLM. These tests pin down its contract: it always
returns :class:`~core.results.Ok`, its output is stable for a given input, it
derives readable text from the image filename (falling back to the page title,
then a non-empty default), and it honors ``max_length`` by truncating on a word
boundary — never mid-word.
"""

from __future__ import annotations

from ai_generator import DeterministicAltTextGenerationService
from core.results import Ok
from core.types import AltTextGenerationInput


def _req(**kw: object) -> AltTextGenerationInput:
    base: dict[str, object] = {"page_url": "https://x/p", "image_url": "https://x/red-bike.jpg"}
    base.update(kw)
    return AltTextGenerationInput(**base)  # type: ignore[arg-type]


def test_derives_readable_text_from_filename() -> None:
    svc = DeterministicAltTextGenerationService()
    result = svc.generate_alt_text(_req(image_url="https://cdn/photos/red-bike.jpg"))
    assert isinstance(result, Ok)
    out = result.unwrap()
    assert out.alt_text == "Red bike"
    assert out.model == "deterministic-alttext-v1"
    assert out.confidence == 0.9


def test_is_deterministic_for_same_input() -> None:
    svc = DeterministicAltTextGenerationService()
    req = _req(image_url="https://x/a_b-c.png")
    first = svc.generate_alt_text(req).unwrap()
    second = svc.generate_alt_text(req).unwrap()
    assert first == second


def test_falls_back_to_page_title_when_filename_has_no_words() -> None:
    svc = DeterministicAltTextGenerationService()
    # A URL with no filename component (nothing to derive words from) falls back
    # to the page title.
    out = svc.generate_alt_text(
        _req(image_url="https://x/", page_title="Our Team")
    ).unwrap()
    assert out.alt_text == "Our Team"


def test_falls_back_to_non_empty_default() -> None:
    svc = DeterministicAltTextGenerationService()
    out = svc.generate_alt_text(_req(image_url="", page_title=None)).unwrap()
    assert out.alt_text.strip() != ""


def test_honors_max_length_on_word_boundary() -> None:
    svc = DeterministicAltTextGenerationService()
    # A long, multi-word filename that would exceed a tiny budget.
    long_name = "https://x/" + "-".join(["word"] * 20) + ".jpg"
    out = svc.generate_alt_text(_req(image_url=long_name, max_length=20)).unwrap()
    assert len(out.alt_text) <= 20
    # Never ends mid-word: the truncation cuts back to a whole word.
    assert not out.alt_text.endswith("wor")


def test_configurable_model_and_confidence() -> None:
    svc = DeterministicAltTextGenerationService(model="m-2", confidence=None)
    out = svc.generate_alt_text(_req()).unwrap()
    assert out.model == "m-2"
    assert out.confidence is None
