"""Property 23 — Unresolvable missing-alt-text yields a report-only fix
retaining the issue.

Feature: website-orchestrator-milestone-0, Property 23: Unresolvable
missing-alt-text yields a report-only fix retaining the issue

Validates: Requirements 5.5

Requirement 5.5: WHERE the Issue type is missing_alt_text and no resolvable
media identifier can be extracted for the affected image, THE Fix_Generator
SHALL produce a report-only SuggestedFix (``auto_applicable=0``) whose reason
records that the media identifier could not be resolved, retaining the
originating Issue reference.

This property drives :meth:`fix_generator.FixGenerator.generate_fix` with a
``missing_alt_text`` :class:`~core.types.Issue` whose
:class:`~core.types.CrawledPage` is *genuinely unresolvable*. The generator
resolves an image (media_id token → filename → first image missing alt → first
image) and then produces a report-only fix when the resolved image is ``None``,
has ``media_id is None``, or has a blank/whitespace ``filename``.

Unresolvability is guaranteed by construction: no image on the page ever has
BOTH a non-``None`` ``media_id`` AND a non-blank ``filename``. Every image is
one of two shapes — ``media_id is None`` (filename arbitrary), or a blank /
whitespace ``filename`` (media_id arbitrary) — so *whichever* image the
generator resolves to fails the resolvability check. The empty-image page is
covered too (``min_size=0``). The issue's ``detail.element`` is varied to
actively reference an image by media_id token or filename, proving that no
element form can accidentally make the page resolvable.
"""

from __future__ import annotations

from datetime import datetime, timezone

from hypothesis import given, settings
from hypothesis import strategies as st

from core.types import (
    CrawledPage,
    FixStatus,
    ImageRef,
    Issue,
    IssueDetail,
    IssueType,
    Severity,
)
from fix_generator import FixGenerator

# --- Strategies ---------------------------------------------------------------

# Non-empty identifier text for Issue.id / tenant_id.
_ids = st.text(min_size=1, max_size=24).filter(lambda s: s.strip() != "")

# Blank / whitespace-only filenames the generator treats as "no usable filename".
_blank_filenames = st.sampled_from(["", " ", "   ", "\t", "\n", "  \t \n "])

# Arbitrary filenames (may or may not be blank) — used only where media_id is
# already None, so resolvability is impossible regardless of the filename.
_any_filenames = st.text(max_size=40)

# Positive media ids (non-None) — used only where the filename is blank.
_media_ids = st.integers(min_value=1, max_value=10_000_000)

# Existing alt text on the image (missing / blank flavours plus a present one).
_alt_text = st.sampled_from([None, "", "   ", "already has alt"])


@st.composite
def _unresolvable_image(draw: st.DrawFn) -> ImageRef:
    """An :class:`ImageRef` that can never be resolved to a writable target.

    Exactly one of two shapes is produced, and neither has BOTH a non-``None``
    ``media_id`` AND a non-blank ``filename``:

    * ``media_id is None`` with an arbitrary (possibly non-blank) filename, or
    * a blank / whitespace filename with an arbitrary (possibly non-``None``)
      media_id.
    """
    if draw(st.booleans()):
        # Shape 1: no media identifier at all; filename is irrelevant.
        return ImageRef(
            media_id=None,
            filename=draw(_any_filenames),
            alt_text=draw(_alt_text),
        )
    # Shape 2: has a media_id but no usable filename.
    return ImageRef(
        media_id=draw(_media_ids),
        filename=draw(_blank_filenames),
        alt_text=draw(_alt_text),
    )


# 0..5 unresolvable images (min_size=0 covers the empty-page case) and mixtures
# of both unresolvable shapes.
_unresolvable_images = st.lists(_unresolvable_image(), min_size=0, max_size=5)

# How the triggering element points at the page; each mode is still unresolvable.
_ELEMENT_MODE_NONE = "none"
_ELEMENT_MODE_UNRELATED = "unrelated"
_ELEMENT_MODE_REF_MEDIA_ID = "ref_media_id"
_ELEMENT_MODE_REF_FILENAME = "ref_filename"
_element_modes = st.sampled_from(
    [
        _ELEMENT_MODE_NONE,
        _ELEMENT_MODE_UNRELATED,
        _ELEMENT_MODE_REF_MEDIA_ID,
        _ELEMENT_MODE_REF_FILENAME,
    ]
)


def _build_element(images: list[ImageRef], mode: str) -> str | None:
    """Construct an ``IssueDetail.element`` that tries to point at an image.

    Even when it references a real media_id token or filename, the referenced
    image is unresolvable by construction, so the page stays unresolvable.
    """
    if mode == _ELEMENT_MODE_NONE:
        return None
    if mode == _ELEMENT_MODE_UNRELATED:
        return "body > figure img.hero"
    if mode == _ELEMENT_MODE_REF_MEDIA_ID:
        for image in images:
            if image.media_id is not None:
                return f"<img> media_id={image.media_id}"
        return "body > figure img.hero"
    # _ELEMENT_MODE_REF_FILENAME
    for image in images:
        if image.filename.strip() != "":
            return f"image element referencing {image.filename}"
    return "body > figure img.hero"


@settings(max_examples=200)
@given(
    images=_unresolvable_images,
    issue_id=_ids,
    tenant_id=_ids,
    severity=st.sampled_from(list(Severity)),
    description=st.text(min_size=1, max_size=80).filter(lambda s: s.strip() != ""),
    page_url=st.text(min_size=1, max_size=60).filter(lambda s: s.strip() != ""),
    element_mode=_element_modes,
)
def test_property_23_unresolvable_alt_text_yields_report_only_fix(
    images: list[ImageRef],
    issue_id: str,
    tenant_id: str,
    severity: Severity,
    description: str,
    page_url: str,
    element_mode: str,
) -> None:
    """For any unresolvable missing-alt-text Issue, ``generate_fix`` returns a
    report-only SuggestedFix (``auto_applicable=0``, ``fix_type=None``,
    ``proposed_value=None``) whose reason records that the media identifier could
    not be resolved, retaining the originating Issue reference, status pending.

    Feature: website-orchestrator-milestone-0, Property 23: Unresolvable
    missing-alt-text yields a report-only fix retaining the issue

    Validates: Requirements 5.5
    """
    element = _build_element(images, element_mode)

    issue = Issue(
        id=issue_id,
        tenant_id=tenant_id,
        issue_type=IssueType.MISSING_ALT_TEXT,
        severity=severity,
        description=description,
        detail=IssueDetail(page_url=page_url, element=element),
        ignored=False,
    )

    page = CrawledPage(
        url=page_url,
        final_url=page_url,
        status_code=200,
        images=images,
        crawled_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )

    fix = FixGenerator().generate_fix(issue, page)

    # A report-only fix must be produced (never None for a missing-alt-text issue).
    assert fix is not None

    # Req 5.5 — report-only: not auto-applicable, no fix type, no proposed value,
    # and no write target.
    assert fix.auto_applicable == 0
    assert fix.fix_type is None
    assert fix.proposed_value is None
    assert fix.target_ref is None

    # Req 5.5 — human-readable reason indicating the media identifier could not
    # be resolved.
    assert fix.reason is not None
    reason_lower = fix.reason.lower()
    assert "resolve" in reason_lower
    assert "media" in reason_lower

    # Req 5.5 — retains the originating Issue reference and tenant, status pending.
    assert fix.issue_id == issue.id
    assert fix.tenant_id == issue.tenant_id
    assert fix.status == FixStatus.PENDING
