"""StructuralEditor — DOM-based edit operations (Milestone 4).

Asserts every operation edits the real DOM structurally (never via a regex over
the raw markup), preserves the fragment shape (no ``<html><body>`` wrapping,
which would corrupt WordPress content), and fails closed with
:class:`~core.exceptions.EditTargetNotFoundError` when the requested target is
absent.
"""
from __future__ import annotations

import json

import pytest
from bs4 import BeautifulSoup

from core.exceptions import EditTargetNotFoundError
from editing.editor import (
    InsertInternalLink,
    InsertSchema,
    ReplaceContentBlock,
    StructuralEditor,
    UpdateAnchorText,
    UpdateHeading,
)

PAGE = (
    "<h1>Our Services</h1>"
    "<p>We offer SEO consulting for small businesses.</p>"
    '<p>Read our <a href="https://x.com/old-guide">old guide</a> for tips.</p>'
    "<h2>Pricing</h2>"
    "<p>Contact us for a quote.</p>"
)


@pytest.fixture()
def editor() -> StructuralEditor:
    return StructuralEditor()


# --- Fragment fidelity (no lxml-style <html><body> wrapping) -----------------


def test_editor_never_wraps_fragment_in_html_body(editor: StructuralEditor) -> None:
    result = editor.update_heading(PAGE, UpdateHeading(level=1, new_text="Our Amazing Services"))
    assert "<html" not in result.lower()
    assert "<body" not in result.lower()


# --- insert_internal_link -----------------------------------------------------


def test_insert_internal_link_after_matching_text(editor: StructuralEditor) -> None:
    edit = InsertInternalLink(
        href="https://x.com/pricing-guide",
        anchor_text="pricing guide",
        after_text="SEO consulting for small businesses",
    )
    result = editor.insert_internal_link(PAGE, edit)
    soup = BeautifulSoup(result, "html.parser")
    new_link = soup.find("a", href="https://x.com/pricing-guide")
    assert new_link is not None
    assert new_link.get_text() == "pricing guide"
    # Inserted right after the paragraph containing the anchor text, not at a
    # guessed location.
    consulting_p = soup.find("p", string=lambda s: s and "SEO consulting" in s)
    assert consulting_p.find_next_sibling().find("a") == new_link


def test_insert_internal_link_appends_when_no_anchor_given(editor: StructuralEditor) -> None:
    edit = InsertInternalLink(href="https://x.com/faq", anchor_text="our FAQ")
    result = editor.insert_internal_link(PAGE, edit)
    soup = BeautifulSoup(result, "html.parser")
    # Last element in the document is the new link's wrapping paragraph.
    assert soup.contents[-1].find("a")["href"] == "https://x.com/faq"


def test_insert_internal_link_missing_anchor_text_raises(editor: StructuralEditor) -> None:
    edit = InsertInternalLink(
        href="https://x.com/x", anchor_text="x", after_text="nonexistent phrase"
    )
    with pytest.raises(EditTargetNotFoundError):
        editor.insert_internal_link(PAGE, edit)


def test_insert_internal_link_preserves_existing_content(editor: StructuralEditor) -> None:
    edit = InsertInternalLink(href="https://x.com/new", anchor_text="new page")
    result = editor.insert_internal_link(PAGE, edit)
    assert "Our Services" in result
    assert "old guide" in result
    assert "Pricing" in result


# --- update_anchor_text -------------------------------------------------------


def test_update_anchor_text_rewrites_matching_href(editor: StructuralEditor) -> None:
    edit = UpdateAnchorText(href="https://x.com/old-guide", new_anchor_text="complete pricing guide")
    result = editor.update_anchor_text(PAGE, edit)
    soup = BeautifulSoup(result, "html.parser")
    link = soup.find("a", href="https://x.com/old-guide")
    assert link.get_text() == "complete pricing guide"
    # href itself is untouched — only the anchor text changes.
    assert link["href"] == "https://x.com/old-guide"


def test_update_anchor_text_missing_href_raises(editor: StructuralEditor) -> None:
    edit = UpdateAnchorText(href="https://x.com/does-not-exist", new_anchor_text="x")
    with pytest.raises(EditTargetNotFoundError):
        editor.update_anchor_text(PAGE, edit)


# --- insert_schema -------------------------------------------------------------


def test_insert_schema_appends_new_jsonld_block(editor: StructuralEditor) -> None:
    edit = InsertSchema(schema_type="FAQPage", data={"mainEntity": []})
    result = editor.insert_schema(PAGE, edit)
    soup = BeautifulSoup(result, "html.parser")
    scripts = soup.find_all("script", attrs={"type": "application/ld+json"})
    assert len(scripts) == 1
    payload = json.loads(scripts[0].string)
    assert payload["@type"] == "FAQPage"
    assert payload["@context"] == "https://schema.org"
    assert payload["mainEntity"] == []


def test_insert_schema_replaces_existing_block_of_same_type(editor: StructuralEditor) -> None:
    first = editor.insert_schema(PAGE, InsertSchema(schema_type="Organization", data={"name": "Old"}))
    second = editor.insert_schema(first, InsertSchema(schema_type="Organization", data={"name": "New"}))
    soup = BeautifulSoup(second, "html.parser")
    scripts = soup.find_all("script", attrs={"type": "application/ld+json"})
    # Replaced in place, never duplicated.
    assert len(scripts) == 1
    assert json.loads(scripts[0].string)["name"] == "New"


def test_insert_schema_does_not_disturb_a_different_existing_type(editor: StructuralEditor) -> None:
    with_org = editor.insert_schema(PAGE, InsertSchema(schema_type="Organization", data={"name": "Acme"}))
    with_both = editor.insert_schema(with_org, InsertSchema(schema_type="FAQPage", data={}))
    soup = BeautifulSoup(with_both, "html.parser")
    scripts = soup.find_all("script", attrs={"type": "application/ld+json"})
    assert len(scripts) == 2
    types = {json.loads(s.string)["@type"] for s in scripts}
    assert types == {"Organization", "FAQPage"}


# --- update_heading ------------------------------------------------------------


def test_update_heading_by_index(editor: StructuralEditor) -> None:
    result = editor.update_heading(PAGE, UpdateHeading(level=1, new_text="New H1", index=0))
    soup = BeautifulSoup(result, "html.parser")
    assert soup.find("h1").get_text() == "New H1"


def test_update_heading_by_match_text(editor: StructuralEditor) -> None:
    result = editor.update_heading(PAGE, UpdateHeading(level=2, new_text="Our Pricing Plans", match_text="Pricing"))
    soup = BeautifulSoup(result, "html.parser")
    assert soup.find("h2").get_text() == "Our Pricing Plans"


def test_update_heading_missing_target_raises(editor: StructuralEditor) -> None:
    with pytest.raises(EditTargetNotFoundError):
        editor.update_heading(PAGE, UpdateHeading(level=3, new_text="x", index=0))


def test_update_heading_invalid_level_raises(editor: StructuralEditor) -> None:
    with pytest.raises(EditTargetNotFoundError):
        editor.update_heading(PAGE, UpdateHeading(level=7, new_text="x"))


# --- replace_content_block -----------------------------------------------------


def test_replace_content_block_replaces_inner_html_structurally(editor: StructuralEditor) -> None:
    edit = ReplaceContentBlock(selector="h2", new_html="Updated Pricing")
    result = editor.replace_content_block(PAGE, edit)
    soup = BeautifulSoup(result, "html.parser")
    assert soup.find("h2").get_text() == "Updated Pricing"


def test_replace_content_block_missing_selector_raises(editor: StructuralEditor) -> None:
    with pytest.raises(EditTargetNotFoundError):
        editor.replace_content_block(PAGE, ReplaceContentBlock(selector=".does-not-exist", new_html="x"))
