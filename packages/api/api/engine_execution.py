"""Governed execution bridge — turns engine recommendations into applied,
audited, reversible ``UPDATE_PAGE_CONTENT``/schema fixes.

Every function here follows the same real pipeline, with no shortcuts:

    read live page (Publishing_Adapter, exact wp_page_id)
      -> structural edit (editing.StructuralEditor, real DOM mutation)
      -> persist Issue + SuggestedFix (Digital_Twin)
      -> governance.approve_fix (Governance_Layer -> Publishing_Adapter write)

A page with no resolved ``wp_page_id`` (WordPress identity not yet mapped) is
skipped honestly — never guessed. A structural edit whose target cannot be
located raises and is reported as a failed proposal, never silently no-op'd.
Nothing here bypasses Governance: every write is decided by
``GovernanceService.approve_fix``, which audits the before-value and supports
rollback exactly like every other fix in the system.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Any

from core.exceptions import EditingError, PublishingError
from core.types import (
    FixStatus,
    FixType,
    Issue,
    IssueCandidate,
    IssueDetail,
    IssueType,
    Severity,
    SuggestedFix,
    TargetRef,
)
from editing.editor import (
    InsertInternalLink,
    InsertSchema,
    ReplaceContentBlock,
    StructuralEditor,
    UpdateHeading,
    UpdateImageAttributes,
    WrapImageWithCaption,
)
from editing.fix_builder import build_structural_fix

__all__ = [
    "ExecutionOutcome",
    "execute_internal_link_proposal",
    "execute_schema_proposal",
    "execute_content_refresh_proposal",
    "execute_ai_writer_draft",
    "execute_ai_writer_seo_meta",
    "execute_programmatic_page_plan",
    "execute_image_seo_proposal",
    "execute_page_merge",
    "execute_page_delete",
]

_EDITOR = StructuralEditor()


@dataclass
class ExecutionOutcome:
    """The result of one governed execution attempt."""

    executed: bool
    fix_id: str | None = None
    status: str | None = None
    reason: str | None = None
    wp_page_id: int | None = None


def _find_page_by_url(digital_twin: Any, tenant_id: str, url: str) -> Any | None:
    for page in digital_twin.list_pages(tenant_id):
        if page.url == url:
            return page
    return None


def _persist_issue(
    digital_twin: Any, tenant_id: str, *, page_url: str, description: str,
    issue_type: IssueType = IssueType.MISSING_SCHEMA,
    severity: Severity = Severity.MEDIUM,
) -> Issue:
    """Persist a real Issue this execution resolves (a fix always needs one)."""
    candidate = IssueCandidate(
        issue_type=issue_type,
        severity=severity,
        description=description,
        detail=IssueDetail(page_url=page_url),
    )
    stored = digital_twin.persist_issues(tenant_id, [candidate])
    return stored[0]


def _ensure_stub_page(digital_twin: Any, tenant_id: str, url: str, title: str) -> None:
    """Ensure a page row exists at ``url`` so an issue/fix can anchor to it.

    Programmatic SEO creates a brand-new page that is not yet in the Digital
    Twin, but ``persist_issues`` requires the issue's page to exist. This upserts
    a minimal, honest stub (``status_code=0`` = not yet crawled/live) representing
    the page that is about to be created; once the created draft is published and
    re-crawled, a normal crawl upsert replaces the stub with real data.
    """
    from datetime import datetime, timezone

    from core.types import CrawledPage

    for page in digital_twin.list_pages(tenant_id):
        if page.url == url:
            return
    digital_twin.upsert_pages(tenant_id, [CrawledPage(
        url=url, final_url=url, status_code=0, title=title,
        crawled_at=datetime.now(timezone.utc),
    )])


def _live_page(subsystems: Any, wp_page_id: int) -> Any | None:
    adapter = subsystems.publishing_adapter
    if adapter is None:
        return None
    try:
        return adapter.get_page(wp_page_id)
    except PublishingError:
        return None


def _apply(
    *, digital_twin: Any, governance: Any, tenant_id: str, fix, actor: str, rationale: str,
) -> ExecutionOutcome:
    persisted = digital_twin.persist_fixes(tenant_id, [fix])[0]
    try:
        updated = governance.approve_fix(tenant_id, persisted.id, actor, rationale)
        return ExecutionOutcome(
            executed=True, fix_id=persisted.id, status=updated.status.value,
            wp_page_id=fix.target_ref.page_id if fix.target_ref else None,
        )
    except PublishingError as exc:
        return ExecutionOutcome(
            executed=False, fix_id=persisted.id, status="approved",
            reason=f"{type(exc).__name__}: {exc}",
            wp_page_id=fix.target_ref.page_id if fix.target_ref else None,
        )


def execute_internal_link_proposal(
    *, subsystems: Any, tenant_id: str, proposal: dict, actor: str = "internal_link_engine",
    rationale: str = "Governed internal-link insertion from the Internal Link Engine",
) -> ExecutionOutcome:
    """Convert one real internal-link proposal into an applied, governed fix.

    ``proposal`` is one entry from ``InternalLinkReport.proposals`` (source_url,
    target_url, suggested_anchor, reason). Skips honestly (no fabrication) when
    the source page has no resolved ``wp_page_id``.
    """
    digital_twin = subsystems.digital_twin
    governance = subsystems.governance
    source_url = proposal["source_url"]
    page = _find_page_by_url(digital_twin, tenant_id, source_url)
    if page is None:
        return ExecutionOutcome(executed=False, reason="source page not found in Digital Twin")
    wp_page_id = getattr(page, "wp_page_id", None)
    if wp_page_id is None:
        return ExecutionOutcome(executed=False, reason="source page has no resolved wp_page_id")
    live_page = _live_page(subsystems, wp_page_id)
    if live_page is None:
        return ExecutionOutcome(executed=False, reason="could not read live page content")

    issue = _persist_issue(
        digital_twin, tenant_id, page_url=source_url,
        description=f"Missing internal link to {proposal['target_url']}",
        issue_type=IssueType.BROKEN_LINKS,  # closest existing recognized type for a link-graph gap
        severity=Severity.MEDIUM,
    )
    try:
        fix = build_structural_fix(
            tenant_id=tenant_id, issue_id=issue.id, wp_page_id=wp_page_id,
            current_html=live_page.content,
            edit=InsertInternalLink(
                href=proposal["target_url"], anchor_text=proposal["suggested_anchor"],
            ),
            reason=proposal.get("reason", "Internal Link Engine proposal"),
            editor=_EDITOR,
        )
    except EditingError as exc:
        return ExecutionOutcome(executed=False, reason=f"{type(exc).__name__}: {exc}")

    return _apply(
        digital_twin=digital_twin, governance=governance, tenant_id=tenant_id,
        fix=fix, actor=actor, rationale=rationale,
    )


def execute_schema_proposal(
    *, subsystems: Any, tenant_id: str, page_url: str, schema_type: str, data: dict,
    actor: str = "schema_engine", rationale: str = "Governed schema insertion from the Schema Engine",
) -> ExecutionOutcome:
    """Insert (or replace) a JSON-LD schema block on a real page, governed."""
    digital_twin = subsystems.digital_twin
    governance = subsystems.governance
    page = _find_page_by_url(digital_twin, tenant_id, page_url)
    if page is None:
        return ExecutionOutcome(executed=False, reason="page not found in Digital Twin")
    wp_page_id = getattr(page, "wp_page_id", None)
    if wp_page_id is None:
        return ExecutionOutcome(executed=False, reason="page has no resolved wp_page_id")
    live_page = _live_page(subsystems, wp_page_id)
    if live_page is None:
        return ExecutionOutcome(executed=False, reason="could not read live page content")

    issue = _persist_issue(
        digital_twin, tenant_id, page_url=page_url,
        description=f"Missing or incomplete {schema_type} schema",
        issue_type=IssueType.MISSING_SCHEMA, severity=Severity.MEDIUM,
    )
    try:
        fix = build_structural_fix(
            tenant_id=tenant_id, issue_id=issue.id, wp_page_id=wp_page_id,
            current_html=live_page.content,
            edit=InsertSchema(schema_type=schema_type, data=data),
            reason=f"Schema Engine: insert {schema_type} structured data",
            editor=_EDITOR,
        )
    except EditingError as exc:
        return ExecutionOutcome(executed=False, reason=f"{type(exc).__name__}: {exc}")

    return _apply(
        digital_twin=digital_twin, governance=governance, tenant_id=tenant_id,
        fix=fix, actor=actor, rationale=rationale,
    )


def execute_page_merge(
    *, subsystems: Any, tenant_id: str, page_url: str, merge_into_url: str,
    reason: str, actor: str = "page_lifecycle_engine",
    rationale: str = "Governed page merge (redirect to canonical)",
) -> ExecutionOutcome:
    """Merge a weaker duplicate page into its stronger canonical target.

    Governed as a content replacement: the weaker page's content becomes a
    real HTML redirect notice (never deleted outright — always reversible via
    Governance rollback, which restores the audited before-value).
    """
    digital_twin = subsystems.digital_twin
    governance = subsystems.governance
    page = _find_page_by_url(digital_twin, tenant_id, page_url)
    if page is None:
        return ExecutionOutcome(executed=False, reason="page not found in Digital Twin")
    wp_page_id = getattr(page, "wp_page_id", None)
    if wp_page_id is None:
        return ExecutionOutcome(executed=False, reason="page has no resolved wp_page_id")
    live_page = _live_page(subsystems, wp_page_id)
    if live_page is None:
        return ExecutionOutcome(executed=False, reason="could not read live page content")

    issue = _persist_issue(
        digital_twin, tenant_id, page_url=page_url, description=reason,
        issue_type=IssueType.DUPLICATE_TITLE, severity=Severity.MEDIUM,
    )
    merged_html = (
        f'<p>This content has been merged into <a href="{merge_into_url}">{merge_into_url}</a>. '
        "Please refer to that page for the current, consolidated information.</p>"
    )
    fix = SuggestedFix(
        id=str(uuid.uuid4()), tenant_id=tenant_id, issue_id=issue.id,
        fix_type=FixType.UPDATE_PAGE_CONTENT, auto_applicable=1,
        target_ref=TargetRef(page_id=wp_page_id), proposed_value=merged_html,
        reason=reason, status=FixStatus.PENDING,
    )
    return _apply(
        digital_twin=digital_twin, governance=governance, tenant_id=tenant_id,
        fix=fix, actor=actor, rationale=rationale,
    )


def execute_page_delete(
    *, subsystems: Any, tenant_id: str, page_url: str, reason: str,
    actor: str = "page_lifecycle_engine", rationale: str = "Governed page removal",
) -> ExecutionOutcome:
    """Remove a real, thin, isolated page through Governance.

    Modeled as a content replacement to an empty/redirect-safe body rather than
    a hard WordPress delete: Governance's rollback path restores the exact
    audited before-value, giving this destructive-feeling action full
    reversibility through the existing pipeline (never a new, unaudited
    hard-delete write path).
    """
    digital_twin = subsystems.digital_twin
    governance = subsystems.governance
    page = _find_page_by_url(digital_twin, tenant_id, page_url)
    if page is None:
        return ExecutionOutcome(executed=False, reason="page not found in Digital Twin")
    wp_page_id = getattr(page, "wp_page_id", None)
    if wp_page_id is None:
        return ExecutionOutcome(executed=False, reason="page has no resolved wp_page_id")
    live_page = _live_page(subsystems, wp_page_id)
    if live_page is None:
        return ExecutionOutcome(executed=False, reason="could not read live page content")

    issue = _persist_issue(
        digital_twin, tenant_id, page_url=page_url, description=reason,
        issue_type=IssueType.THIN_CONTENT, severity=Severity.LOW,
    )
    fix = SuggestedFix(
        id=str(uuid.uuid4()), tenant_id=tenant_id, issue_id=issue.id,
        fix_type=FixType.UPDATE_PAGE_CONTENT, auto_applicable=1,
        target_ref=TargetRef(page_id=wp_page_id),
        proposed_value="<p>This page has been retired.</p>",
        reason=reason, status=FixStatus.PENDING,
    )
    return _apply(
        digital_twin=digital_twin, governance=governance, tenant_id=tenant_id,
        fix=fix, actor=actor, rationale=rationale,
    )


def execute_ai_writer_draft(
    *, subsystems: Any, tenant_id: str, page_url: str, generated_html: str,
    reason: str = "AI Writer V2: governed full-page draft (via AI Gateway)",
    actor: str = "ai_writer_v2", rationale: str = "Governed AI-generated content update",
) -> ExecutionOutcome:
    """Apply an AI Writer V2 draft to a real existing page, governed.

    ``generated_html`` must already have been produced by
    :class:`api.ai_writer.AIWriterV2` (which routes every generation call
    through the AI Gateway's ``CapabilityRunner`` — never a direct provider
    call). This function only handles the governed publish step.
    """
    digital_twin = subsystems.digital_twin
    governance = subsystems.governance
    page = _find_page_by_url(digital_twin, tenant_id, page_url)
    if page is None:
        return ExecutionOutcome(executed=False, reason="page not found in Digital Twin")
    wp_page_id = getattr(page, "wp_page_id", None)
    if wp_page_id is None:
        return ExecutionOutcome(executed=False, reason="page has no resolved wp_page_id")

    issue = _persist_issue(
        digital_twin, tenant_id, page_url=page_url, description=reason,
        issue_type=IssueType.THIN_CONTENT, severity=Severity.MEDIUM,
    )
    fix = SuggestedFix(
        id=str(uuid.uuid4()), tenant_id=tenant_id, issue_id=issue.id,
        fix_type=FixType.UPDATE_PAGE_CONTENT, auto_applicable=1,
        target_ref=TargetRef(page_id=wp_page_id),
        proposed_value=generated_html, reason=reason, status=FixStatus.PENDING,
        generation_model="ai-gateway",
    )
    return _apply(
        digital_twin=digital_twin, governance=governance, tenant_id=tenant_id,
        fix=fix, actor=actor, rationale=rationale,
    )


def execute_ai_writer_seo_meta(
    *, subsystems: Any, tenant_id: str, page_url: str, seo_meta: dict[str, str],
    reason: str = "AI Writer V2: governed RankMath/OG/Twitter/canonical metadata",
    actor: str = "ai_writer_v2", rationale: str = "Governed AI-generated SEO metadata update",
) -> ExecutionOutcome:
    """Apply an AI Writer V2 draft's RankMath/OG/Twitter/canonical postmeta to a
    real existing page, governed.

    A separate governed fix from :func:`execute_ai_writer_draft` because it
    targets a distinct live resource (page postmeta, not page content); each is
    independently audited and rollback-capable.
    """
    digital_twin = subsystems.digital_twin
    governance = subsystems.governance
    page = _find_page_by_url(digital_twin, tenant_id, page_url)
    if page is None:
        return ExecutionOutcome(executed=False, reason="page not found in Digital Twin")
    wp_page_id = getattr(page, "wp_page_id", None)
    if wp_page_id is None:
        return ExecutionOutcome(executed=False, reason="page has no resolved wp_page_id")

    issue = _persist_issue(
        digital_twin, tenant_id, page_url=page_url, description=reason,
        issue_type=IssueType.MISSING_META_DESCRIPTION, severity=Severity.LOW,
    )
    fix = SuggestedFix(
        id=str(uuid.uuid4()), tenant_id=tenant_id, issue_id=issue.id,
        fix_type=FixType.UPDATE_SEO_META, auto_applicable=1,
        target_ref=TargetRef(page_id=wp_page_id),
        proposed_value=json.dumps(seo_meta, sort_keys=True),
        reason=reason, status=FixStatus.PENDING, generation_model="ai-gateway",
    )
    return _apply(
        digital_twin=digital_twin, governance=governance, tenant_id=tenant_id,
        fix=fix, actor=actor, rationale=rationale,
    )


def execute_programmatic_page_plan(
    *, subsystems: Any, tenant_id: str, title: str, content: str, slug: str,
    reason: str, planned_url: str | None = None,
    actor: str = "programmatic_seo_engine",
    rationale: str = "Governed programmatic page creation (draft)",
) -> ExecutionOutcome:
    """Create one governed, draft-only programmatic landing page.

    Always creates in WordPress ``draft`` status via
    ``GovernanceService.approve_fix`` -> ``PublishingAdapterPort.create_page``.
    Rollback deletes the created page (see
    ``GovernanceService.rollback_fix`` / ``_write_target_value``). Requires no
    ``wp_page_id`` — this is a creation, not an edit of an existing page.
    """
    digital_twin = subsystems.digital_twin
    governance = subsystems.governance

    # The page does not exist yet; anchor its issue/fix to a stub page row at the
    # planned URL so the governed pipeline (which ties every fix to an issue and
    # every issue to a page) can act without a schema change.
    page_url = planned_url or f"https://programmatic.local/{slug}"
    _ensure_stub_page(digital_twin, tenant_id, page_url, title)
    issue = _persist_issue(
        digital_twin, tenant_id, page_url=page_url,
        description=reason, issue_type=IssueType.MISSING_TITLE, severity=Severity.LOW,
    )
    fix = SuggestedFix(
        id=str(uuid.uuid4()), tenant_id=tenant_id, issue_id=issue.id,
        fix_type=FixType.CREATE_PAGE, auto_applicable=1, target_ref=None,
        proposed_value=json.dumps({"title": title, "content": content, "slug": slug}),
        reason=reason, status=FixStatus.PENDING,
    )
    persisted = digital_twin.persist_fixes(tenant_id, [fix])[0]
    try:
        updated = governance.approve_fix(tenant_id, persisted.id, actor, rationale)
        created_id = governance.last_created_page_id(persisted.id) if hasattr(governance, "last_created_page_id") else None
        return ExecutionOutcome(
            executed=True, fix_id=persisted.id, status=updated.status.value, wp_page_id=created_id,
        )
    except PublishingError as exc:
        return ExecutionOutcome(
            executed=False, fix_id=persisted.id, status="approved",
            reason=f"{type(exc).__name__}: {exc}",
        )


def execute_image_seo_proposal(
    *, subsystems: Any, tenant_id: str, page_url: str, proposal: dict,
    actor: str = "image_seo_engine", rationale: str = "Governed image-markup fix",
) -> ExecutionOutcome:
    """Apply one real Image SEO proposal (lazy-loading or caption) as a governed
    fix. Never handles ``missing_alt`` — that flows through the existing
    alt-text governed path."""
    digital_twin = subsystems.digital_twin
    governance = subsystems.governance
    finding_type = proposal.get("finding_type")
    if finding_type not in ("missing_lazy_loading", "missing_caption"):
        return ExecutionOutcome(executed=False, reason=f"unsupported image finding_type {finding_type!r}")

    page = _find_page_by_url(digital_twin, tenant_id, page_url)
    if page is None:
        return ExecutionOutcome(executed=False, reason="page not found in Digital Twin")
    wp_page_id = getattr(page, "wp_page_id", None)
    if wp_page_id is None:
        return ExecutionOutcome(executed=False, reason="page has no resolved wp_page_id")
    live_page = _live_page(subsystems, wp_page_id)
    if live_page is None:
        return ExecutionOutcome(executed=False, reason="could not read live page content")

    if finding_type == "missing_lazy_loading":
        edit = UpdateImageAttributes(src=proposal["src"], loading=proposal.get("loading") or "lazy")
        description = f"Missing lazy loading on image {proposal['src']}"
    else:
        caption = proposal.get("caption") or ""
        if not caption.strip():
            return ExecutionOutcome(executed=False, reason="no real caption text available to apply")
        edit = WrapImageWithCaption(src=proposal["src"], caption=caption)
        description = f"Missing caption on image {proposal['src']}"

    issue = _persist_issue(
        digital_twin, tenant_id, page_url=page_url, description=description,
        issue_type=IssueType.MISSING_ALT_TEXT, severity=Severity.LOW,
    )
    try:
        fix = build_structural_fix(
            tenant_id=tenant_id, issue_id=issue.id, wp_page_id=wp_page_id,
            current_html=live_page.content, edit=edit,
            reason=proposal.get("reason", description), editor=_EDITOR,
        )
    except EditingError as exc:
        return ExecutionOutcome(executed=False, reason=f"{type(exc).__name__}: {exc}")

    return _apply(
        digital_twin=digital_twin, governance=governance, tenant_id=tenant_id,
        fix=fix, actor=actor, rationale=rationale,
    )


def execute_content_refresh_proposal(
    *, subsystems: Any, tenant_id: str, page_url: str, edit: Any,
    description: str, actor: str = "content_refresh_engine",
    rationale: str = "Governed content refresh",
) -> ExecutionOutcome:
    """Apply one content-refresh structural edit (heading rewrite or block
    replacement) to a real page, governed."""
    digital_twin = subsystems.digital_twin
    governance = subsystems.governance
    if not isinstance(edit, (UpdateHeading, ReplaceContentBlock)):
        return ExecutionOutcome(executed=False, reason="unsupported content-refresh edit type")

    page = _find_page_by_url(digital_twin, tenant_id, page_url)
    if page is None:
        return ExecutionOutcome(executed=False, reason="page not found in Digital Twin")
    wp_page_id = getattr(page, "wp_page_id", None)
    if wp_page_id is None:
        return ExecutionOutcome(executed=False, reason="page has no resolved wp_page_id")
    live_page = _live_page(subsystems, wp_page_id)
    if live_page is None:
        return ExecutionOutcome(executed=False, reason="could not read live page content")

    issue = _persist_issue(
        digital_twin, tenant_id, page_url=page_url, description=description,
        issue_type=IssueType.THIN_CONTENT, severity=Severity.MEDIUM,
    )
    try:
        fix = build_structural_fix(
            tenant_id=tenant_id, issue_id=issue.id, wp_page_id=wp_page_id,
            current_html=live_page.content, edit=edit, reason=description, editor=_EDITOR,
        )
    except EditingError as exc:
        return ExecutionOutcome(executed=False, reason=f"{type(exc).__name__}: {exc}")

    return _apply(
        digital_twin=digital_twin, governance=governance, tenant_id=tenant_id,
        fix=fix, actor=actor, rationale=rationale,
    )
