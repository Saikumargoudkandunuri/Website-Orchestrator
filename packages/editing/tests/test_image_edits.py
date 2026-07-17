"""StructuralEditor image operations (Milestone 5 — Image SEO Engine)."""
from __future__ import annotations

import pytest

from core.exceptions import EditTargetNotFoundError
from editing.editor import StructuralEditor, UpdateImageAttributes, WrapImageWithCaption

PAGE = '<p>intro</p><img src="https://x.com/hero.jpg" alt="Hero"><p>more text</p>'


def test_update_image_attributes_sets_loading_and_dimensions() -> None:
    editor = StructuralEditor()
    result = editor.update_image_attributes(
        PAGE, UpdateImageAttributes(src="https://x.com/hero.jpg", loading="lazy", width="800", height="400"),
    )
    assert 'loading="lazy"' in result
    assert 'width="800"' in result
    assert 'height="400"' in result
    assert "Hero" in result  # alt preserved, never touched


def test_update_image_attributes_missing_src_raises() -> None:
    editor = StructuralEditor()
    with pytest.raises(EditTargetNotFoundError):
        editor.update_image_attributes(PAGE, UpdateImageAttributes(src="https://x.com/missing.jpg", loading="lazy"))


def test_wrap_image_with_caption_creates_figure() -> None:
    editor = StructuralEditor()
    result = editor.wrap_image_with_caption(
        PAGE, WrapImageWithCaption(src="https://x.com/hero.jpg", caption="A real hero shot"),
    )
    assert "<figure>" in result and "<figcaption>A real hero shot</figcaption>" in result
    assert "intro" in result and "more text" in result


def test_wrap_image_with_caption_already_captioned_raises() -> None:
    editor = StructuralEditor()
    captioned = editor.wrap_image_with_caption(
        PAGE, WrapImageWithCaption(src="https://x.com/hero.jpg", caption="first"),
    )
    with pytest.raises(EditTargetNotFoundError):
        editor.wrap_image_with_caption(captioned, WrapImageWithCaption(src="https://x.com/hero.jpg", caption="second"))
