"""Bridge a structural edit to a governed :class:`~core.types.SuggestedFix`.

This is the seam that lets the Internal Link / Schema / Content Refresh engines
go from *recommendation* to *executable*: given the page's current live content,
a WordPress page id, and an edit request, :func:`build_structural_fix` runs the
:class:`~editing.editor.StructuralEditor`, and — on success — returns a
``pending``, auto-applicable ``SuggestedFix`` (``fix_type=UPDATE_PAGE_CONTENT``,
``target_ref.page_id=wp_page_id``, ``proposed_value=<new html>``) ready to be
persisted through the existing Digital_Twin and decided through the existing
Governance_Layer. No new write path is introduced: applying, auditing, and
rolling back this fix reuses the exact pipeline that already governs
``UPDATE_PAGE_CONTENT``.

An edit whose target cannot be located raises
:class:`~core.exceptions.EditTargetNotFoundError` (propagated, not swallowed) so
callers can report a failed proposal honestly instead of silently applying
nothing.
"""
from __future__ import annotations

import uuid
from typing import Any

from core.types import FixStatus, FixType, SuggestedFix, TargetRef

from editing.editor import StructuralEditor

__all__ = ["build_structural_fix"]

_OPERATIONS = {
    "insert_internal_link": "insert_internal_link",
    "update_anchor_text": "update_anchor_text",
    "insert_schema": "insert_schema",
    "update_heading": "update_heading",
    "replace_content_block": "replace_content_block",
}


def build_structural_fix(
    *,
    tenant_id: str,
    issue_id: str,
    wp_page_id: int,
    current_html: str,
    edit: Any,
    reason: str,
    editor: StructuralEditor | None = None,
) -> SuggestedFix:
    """Run one structural edit and wrap the result as a governed page-content fix.

    Args:
        tenant_id: Owning tenant, stamped on the returned fix.
        issue_id: The persisted :class:`~core.types.Issue` this fix resolves —
            required by the Digital_Twin schema (a fix always traces back to an
            issue); engines that propose autonomous improvements must first
            persist a corresponding issue/finding.
        wp_page_id: The resolved live WordPress page/post id (from
            ``DigitalTwinPort.resolve_wp_identities``) — the exact target, never
            guessed from a URL.
        current_html: The page's current live ``content`` (read fresh from the
            Publishing_Adapter before editing, so the edit applies to the real
            current state).
        edit: One of the dataclasses in :mod:`editing.editor`
            (``InsertInternalLink`` / ``UpdateAnchorText`` / ``InsertSchema`` /
            ``UpdateHeading`` / ``ReplaceContentBlock``).
        reason: Human-readable explanation recorded on the fix for the reviewer.
        editor: Optional injected :class:`StructuralEditor` (tests only); a
            fresh one is used by default.

    Returns:
        A ``pending``, auto-applicable ``SuggestedFix`` ready for
        ``DigitalTwinPort.persist_fixes`` and normal Governance approval.

    Raises:
        core.exceptions.EditTargetNotFoundError: the edit's target could not be
            located in ``current_html``; no fix is built.
    """
    engine = editor or StructuralEditor()
    method_name = _dispatch_name(edit)
    method = getattr(engine, method_name)
    new_html = method(current_html, edit)

    return SuggestedFix(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        issue_id=issue_id,
        fix_type=FixType.UPDATE_PAGE_CONTENT,
        auto_applicable=1,
        target_ref=TargetRef(page_id=wp_page_id),
        proposed_value=new_html,
        reason=reason,
        status=FixStatus.PENDING,
    )


def _dispatch_name(edit: Any) -> str:
    """Map an edit dataclass instance to the ``StructuralEditor`` method name."""
    from editing.editor import (
        InsertInternalLink,
        InsertSchema,
        ReplaceContentBlock,
        UpdateAnchorText,
        UpdateHeading,
        UpdateImageAttributes,
        WrapImageWithCaption,
    )

    mapping = {
        InsertInternalLink: "insert_internal_link",
        UpdateAnchorText: "update_anchor_text",
        InsertSchema: "insert_schema",
        UpdateHeading: "update_heading",
        ReplaceContentBlock: "replace_content_block",
        UpdateImageAttributes: "update_image_attributes",
        WrapImageWithCaption: "wrap_image_with_caption",
    }
    for edit_type, name in mapping.items():
        if isinstance(edit, edit_type):
            return name
    raise TypeError(f"Unsupported edit type: {type(edit).__name__}")
