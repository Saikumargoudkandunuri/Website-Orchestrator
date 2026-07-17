"""Editing subsystem — structural (DOM-based) HTML edit operations.

Turns a concrete edit request (insert an internal link, insert a JSON-LD schema
block, update a heading's text, replace a content block) into the *new* full
page HTML plus a governed :class:`~core.types.SuggestedFix` targeting the exact
WordPress page. It never writes to the live site itself — the existing
Governance_Layer / Publishing_Adapter pipeline is the only writer, so every
structural edit is approved, audited, and reversible exactly like every other
``UPDATE_PAGE_CONTENT`` fix.

Editing is a pure transformation, like Fix_Generator: given the current page
HTML and an edit request, it returns the new HTML (or raises a typed
:class:`~core.exceptions.EditingError` when the requested target cannot be
located). It depends only on Core_Package.

No regex-based editing: every operation parses the HTML into a DOM with
:mod:`bs4` (``html.parser`` — never ``lxml``, which wraps a fragment in
``<html><body>`` and would corrupt WordPress content) and mutates the tree
structurally.
"""

from editing.editor import StructuralEditor
from editing.fix_builder import build_structural_fix

__all__ = ["StructuralEditor", "build_structural_fix"]
