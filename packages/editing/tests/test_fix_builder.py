"""build_structural_fix — bridges a structural edit into a governed
:class:`~core.types.SuggestedFix` (Milestone 4).

Proves the resulting fix is a real, governable ``UPDATE_PAGE_CONTENT`` record
targeting the exact WordPress page id — the same shape the existing
Governance_Layer already approves/applies/rolls back (proven in
``packages/governance/tests``) — and that a failed edit raises rather than
silently producing an inert fix.
"""
from __future__ import annotations

import pytest

from core.exceptions import EditTargetNotFoundError
from core.types import FixStatus, FixType

from editing.editor import InsertInternalLink, UpdateHeading
from editing.fix_builder import build_structural_fix

PAGE_HTML = "<h1>Welcome</h1><p>This is the homepage.</p>"


def test_build_structural_fix_produces_governable_page_content_fix() -> None:
    fix = build_structural_fix(
        tenant_id="tenant-a",
        issue_id="issue-1",
        wp_page_id=42,
        current_html=PAGE_HTML,
        edit=InsertInternalLink(href="https://x.com/services", anchor_text="our services"),
        reason="Orphan page needs internal equity from the homepage.",
    )
    assert fix.tenant_id == "tenant-a"
    assert fix.issue_id == "issue-1"
    assert fix.fix_type is FixType.UPDATE_PAGE_CONTENT
    assert fix.auto_applicable == 1
    assert fix.target_ref.page_id == 42
    assert fix.target_ref.media_id is None
    assert fix.status is FixStatus.PENDING
    assert "our services" in fix.proposed_value
    assert "Welcome" in fix.proposed_value  # original content preserved


def test_build_structural_fix_propagates_edit_target_not_found() -> None:
    with pytest.raises(EditTargetNotFoundError):
        build_structural_fix(
            tenant_id="tenant-a",
            issue_id="issue-1",
            wp_page_id=42,
            current_html=PAGE_HTML,
            edit=UpdateHeading(level=3, new_text="x", index=0),
            reason="should not matter",
        )


def test_build_structural_fix_ids_are_unique_per_call() -> None:
    fix_a = build_structural_fix(
        tenant_id="t", issue_id="i", wp_page_id=1, current_html=PAGE_HTML,
        edit=InsertInternalLink(href="https://x.com/a", anchor_text="a"), reason="r",
    )
    fix_b = build_structural_fix(
        tenant_id="t", issue_id="i", wp_page_id=1, current_html=PAGE_HTML,
        edit=InsertInternalLink(href="https://x.com/b", anchor_text="b"), reason="r",
    )
    assert fix_a.id != fix_b.id
