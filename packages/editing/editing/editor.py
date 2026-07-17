"""StructuralEditor — pure, DOM-based HTML edit operations (Milestone 4).

Every operation parses the *current* page HTML into a real DOM
(:mod:`bs4`, ``html.parser``), locates its target structurally (never with a
regex over the raw markup), mutates the tree, and serializes the result back to
HTML. It never touches the live site — it returns the new HTML string for the
caller to wrap in a governed :class:`~core.types.SuggestedFix`
(``fix_type=UPDATE_PAGE_CONTENT``), which the existing Governance_Layer /
Publishing_Adapter pipeline applies, audits, and can roll back exactly like any
other page-content fix.

Parser choice
-------------
``html.parser`` is used deliberately instead of ``lxml``: ``lxml`` wraps a bare
HTML fragment in ``<html><body>...</body></html>`` on serialization, which would
corrupt a WordPress ``post_content`` fragment on write-back. ``html.parser``
round-trips a fragment byte-for-structure, only touching what is explicitly
mutated.

Every operation either succeeds and returns the new HTML, or raises
:class:`~core.exceptions.EditTargetNotFoundError` — it never silently no-ops and
never guesses a fallback location.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from bs4 import BeautifulSoup, Tag

from core.exceptions import EditTargetNotFoundError

__all__ = [
    "StructuralEditor",
    "InsertInternalLink",
    "UpdateAnchorText",
    "InsertSchema",
    "UpdateHeading",
    "ReplaceContentBlock",
    "UpdateImageAttributes",
    "WrapImageWithCaption",
]

_PARSER = "html.parser"


@dataclass(frozen=True)
class InsertInternalLink:
    """Insert a new internal link with the given anchor text and href.

    ``after_text`` locates the text node/paragraph to insert the link after
    (structural match: the first element whose visible text contains it). When
    omitted, the link is appended as a new trailing paragraph.
    """

    href: str
    anchor_text: str
    after_text: str | None = None
    rel: str | None = None


@dataclass(frozen=True)
class UpdateAnchorText:
    """Rewrite the visible text of the first anchor whose ``href`` matches."""

    href: str
    new_anchor_text: str


@dataclass(frozen=True)
class InsertSchema:
    """Insert (or replace) a JSON-LD ``<script type="application/ld+json">``
    block for the given ``@type``.

    If a block already declaring the same ``@type`` exists, it is replaced
    in place (never duplicated); otherwise the new block is appended at the end
    of the document.
    """

    schema_type: str
    data: dict


@dataclass(frozen=True)
class UpdateHeading:
    """Rewrite the text of the ``n``-th heading (0-indexed, document order) at
    ``level`` (1-6), or the first heading matching ``match_text`` when given."""

    level: int
    new_text: str
    index: int = 0
    match_text: str | None = None


@dataclass(frozen=True)
class ReplaceContentBlock:
    """Replace the inner HTML of the first element matching ``selector`` with
    ``new_html`` (parsed structurally, not string-substituted)."""

    selector: str
    new_html: str


@dataclass(frozen=True)
class UpdateImageAttributes:
    """Set/update real image attributes (never ``alt`` — that has its own
    governed heuristic/AI path) on the first ``<img>`` whose ``src`` matches."""

    src: str
    loading: str | None = None
    width: str | None = None
    height: str | None = None


@dataclass(frozen=True)
class WrapImageWithCaption:
    """Wrap the first ``<img>`` whose ``src`` matches in a ``<figure>`` with a
    ``<figcaption>`` carrying real, non-fabricated caption text."""

    src: str
    caption: str


class StructuralEditor:
    """Pure DOM-based transform: current HTML + an edit request -> new HTML."""

    def insert_internal_link(self, html: str, edit: InsertInternalLink) -> str:
        soup = BeautifulSoup(html or "", _PARSER)
        anchor = soup.new_tag("a", href=edit.href)
        if edit.rel:
            anchor["rel"] = edit.rel
        anchor.string = edit.anchor_text

        if edit.after_text:
            target = self._find_text_container(soup, edit.after_text)
            if target is None:
                raise EditTargetNotFoundError(
                    f"Could not locate text {edit.after_text!r} to anchor the "
                    "new internal link after."
                )
            wrapper = soup.new_tag("p")
            wrapper.append(anchor)
            target.insert_after(wrapper)
        else:
            wrapper = soup.new_tag("p")
            wrapper.append(anchor)
            soup.append(wrapper)
        return str(soup)

    def update_anchor_text(self, html: str, edit: UpdateAnchorText) -> str:
        soup = BeautifulSoup(html or "", _PARSER)
        link = self._find_anchor_by_href(soup, edit.href)
        if link is None:
            raise EditTargetNotFoundError(
                f"Could not locate an <a> tag with href={edit.href!r} to "
                "update its anchor text."
            )
        link.clear()
        link.string = edit.new_anchor_text
        return str(soup)

    def insert_schema(self, html: str, edit: InsertSchema) -> str:
        soup = BeautifulSoup(html or "", _PARSER)
        payload = dict(edit.data)
        payload.setdefault("@context", "https://schema.org")
        payload["@type"] = edit.schema_type

        existing = self._find_schema_block(soup, edit.schema_type)
        script = soup.new_tag("script", attrs={"type": "application/ld+json"})
        script.string = json.dumps(payload)
        if existing is not None:
            existing.replace_with(script)
        else:
            soup.append(script)
        return str(soup)

    def update_heading(self, html: str, edit: UpdateHeading) -> str:
        if not 1 <= edit.level <= 6:
            raise EditTargetNotFoundError(
                f"Heading level must be 1-6, got {edit.level!r}."
            )
        soup = BeautifulSoup(html or "", _PARSER)
        tag_name = f"h{edit.level}"
        candidates = soup.find_all(tag_name)
        target: Tag | None = None
        if edit.match_text:
            for candidate in candidates:
                if edit.match_text.strip().lower() in candidate.get_text(strip=True).lower():
                    target = candidate
                    break
        elif 0 <= edit.index < len(candidates):
            target = candidates[edit.index]

        if target is None:
            raise EditTargetNotFoundError(
                f"Could not locate a <{tag_name}> heading to update "
                f"(index={edit.index!r}, match_text={edit.match_text!r})."
            )
        target.clear()
        target.append(edit.new_text)
        return str(soup)

    def replace_content_block(self, html: str, edit: ReplaceContentBlock) -> str:
        soup = BeautifulSoup(html or "", _PARSER)
        target = soup.select_one(edit.selector)
        if target is None:
            raise EditTargetNotFoundError(
                f"Could not locate an element matching selector {edit.selector!r}."
            )
        replacement = BeautifulSoup(edit.new_html or "", _PARSER)
        target.clear()
        for child in list(replacement.contents):
            target.append(child)
        return str(soup)

    def update_image_attributes(self, html: str, edit: UpdateImageAttributes) -> str:
        soup = BeautifulSoup(html or "", _PARSER)
        img = self._find_img_by_src(soup, edit.src)
        if img is None:
            raise EditTargetNotFoundError(
                f"Could not locate an <img> tag with src={edit.src!r} to update."
            )
        if edit.loading:
            img["loading"] = edit.loading
        if edit.width:
            img["width"] = edit.width
        if edit.height:
            img["height"] = edit.height
        return str(soup)

    def wrap_image_with_caption(self, html: str, edit: WrapImageWithCaption) -> str:
        soup = BeautifulSoup(html or "", _PARSER)
        img = self._find_img_by_src(soup, edit.src)
        if img is None:
            raise EditTargetNotFoundError(
                f"Could not locate an <img> tag with src={edit.src!r} to caption."
            )
        if img.find_parent("figure") is not None:
            raise EditTargetNotFoundError(
                f"<img src={edit.src!r}> is already inside a <figure>."
            )
        figure = soup.new_tag("figure")
        figcaption = soup.new_tag("figcaption")
        figcaption.string = edit.caption
        img.replace_with(figure)
        figure.append(img)
        figure.append(figcaption)
        return str(soup)

    # --- Structural lookup helpers --------------------------------------------

    @staticmethod
    def _find_img_by_src(soup: BeautifulSoup, src: str) -> Tag | None:
        for tag in soup.find_all("img", src=True):
            if tag["src"] == src:
                return tag
        return None

    @staticmethod
    def _find_text_container(soup: BeautifulSoup, needle: str) -> Tag | None:
        needle_norm = needle.strip().lower()
        if not needle_norm:
            return None
        for tag in soup.find_all(["p", "li", "h1", "h2", "h3", "h4", "h5", "h6"]):
            if needle_norm in tag.get_text(strip=True).lower():
                return tag
        return None

    @staticmethod
    def _find_anchor_by_href(soup: BeautifulSoup, href: str) -> Tag | None:
        for tag in soup.find_all("a", href=True):
            if tag["href"] == href:
                return tag
        return None

    @staticmethod
    def _find_schema_block(soup: BeautifulSoup, schema_type: str) -> Tag | None:
        for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
            raw = tag.string or tag.get_text()
            if not raw:
                continue
            try:
                data = json.loads(raw)
            except (ValueError, TypeError):
                continue
            types = data.get("@type") if isinstance(data, dict) else None
            values = types if isinstance(types, list) else [types]
            if schema_type in values:
                return tag
        return None
