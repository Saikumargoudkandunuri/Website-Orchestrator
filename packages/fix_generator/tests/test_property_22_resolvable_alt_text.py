"""Property 22 — Resolvable missing-alt-text yields a valid auto-applicable fix.

Feature: website-orchestrator-milestone-0, Property 22: Resolvable missing-alt-text
yields a valid auto-applicable fix

Validates: Requirements 5.3, 5.4

Requirement 5.3: WHERE the Issue type is missing_alt_text and the page contains an
image from which a media identifier and a non-empty image filename can be extracted,
THE Fix_Generator SHALL produce a SuggestedFix with ``auto_applicable=1``,
``fix_type=update_alt_text``, and non-empty heuristic alt text of at most 125
characters derived from the image filename.

Requirement 5.4: THE Fix_Generator SHALL treat filename-derived alt text as a
placeholder heuristic and SHALL NOT represent it as AI-generated content.

This property drives :meth:`fix_generator.FixGenerator.generate_fix` with a
``missing_alt_text`` :class:`~core.types.Issue` whose :class:`~core.types.CrawledPage`
contains a *genuinely resolvable* image — an :class:`~core.types.ImageRef` with a
non-``None`` ``media_id`` and a non-empty ``filename`` that is missing alt text.
Resolvability is guaranteed three ways (varied per example): the issue's
``detail.element`` may reference the image by ``media_id`` token, by filename, or be
unrelated/absent — in every case the resolvable image is the only image on the page
and is missing alt text, so the generator's resolution (media_id token → filename →
first image missing alt → first image) always lands on it and the auto-applicable
branch is taken.

Filenames are generated with extensions, mixed separators, unicode, and
deliberately over-long names to exercise the 125-character truncation.
"""

from __future__ import annotations

from datetime import datetime, timezone

from hypothesis import given, settings
from hypothesis import strategies as st

from core.constants import MAX_ALT_TEXT_LEN
from core.types import (
    CrawledPage,
    FixStatus,
    FixType,
    ImageRef,
    Issue,
    IssueDetail,
    IssueType,
    Severity,
)
from fix_generator import FixGenerator

# --- Strategies ---------------------------------------------------------------

# A broad word alphabet: ASCII letters/digits plus a band of unicode letters
# (Latin-1 supplement / extended) so filenames exercise non-ASCII derivation.
_word = st.text(
    alphabet=st.characters(
        min_codepoint=0x30,
        max_codepoint=0x24F,
        blacklist_categories=("Cc", "Cs", "Zs"),
    ),
    min_size=1,
    max_size=18,
)

# Separators the generator collapses into spaces (plus a literal space and the
# percent-encoded space it also normalizes).
_separators = st.sampled_from(["-", "_", ".", "+", "%20", " "])

# File extensions (including empty and mixed-case) to exercise extension stripping.
_extensions = st.sampled_from(
    ["", ".jpg", ".jpeg", ".png", ".JPEG", ".WebP", ".gif", ".svg", ".JPG"]
)

# Optional path/URL prefixes so the generator's path/query stripping is exercised.
_prefixes = st.sampled_from(
    [
        "",
        "images/",
        "/wp-content/uploads/2024/07/",
        "https://cdn.example.com/a/b/",
        "..\\windows\\path\\",
    ]
)

# Optional query/fragment tails the generator must discard.
_tails = st.sampled_from(["", "?v=2", "#frag", "?w=800&h=600", "?ref=x#y"])


@st.composite
def _normal_filenames(draw: st.DrawFn) -> str:
    """A realistic filename: prefix + separator-joined words + extension + tail."""
    words = draw(st.lists(_word, min_size=1, max_size=6))
    sep = draw(_separators)
    stem = sep.join(words)
    fname = draw(_prefixes) + stem + draw(_extensions) + draw(_tails)
    return fname


@st.composite
def _long_filenames(draw: st.DrawFn) -> str:
    """A deliberately over-long filename whose derived alt text exceeds 125
    characters, so the truncation guarantee (Req 5.4) is exercised."""
    words = draw(st.lists(_word, min_size=12, max_size=40))
    sep = draw(_separators)
    stem = sep.join(words)
    # Ensure the stem is long enough to force truncation after derivation.
    while len(stem) <= MAX_ALT_TEXT_LEN + 10:
        stem = stem + sep + "supplementaryword"
    return stem + draw(_extensions)


# Any filename, filtered to be genuinely non-blank so the auto-applicable branch
# is taken (a blank filename would route to the report-only branch).
_filenames = st.one_of(_normal_filenames(), _long_filenames()).filter(
    lambda f: f.strip() != ""
)

# Non-empty identifier text for Issue.id / tenant_id.
_ids = st.text(min_size=1, max_size=24).filter(lambda s: s.strip() != "")

# Positive media ids so the identifier is always resolvable (non-None).
_media_ids = st.integers(min_value=1, max_value=10_000_000)

# How the triggering element points at the image; every variant still resolves
# to the single missing-alt image on the page.
_ELEMENT_MODE_MEDIA_ID = "media_id"
_ELEMENT_MODE_FILENAME = "filename"
_ELEMENT_MODE_UNRELATED = "unrelated"
_ELEMENT_MODE_NONE = "none"
_element_modes = st.sampled_from(
    [
        _ELEMENT_MODE_MEDIA_ID,
        _ELEMENT_MODE_FILENAME,
        _ELEMENT_MODE_UNRELATED,
        _ELEMENT_MODE_NONE,
    ]
)


@settings(max_examples=200)
@given(
    filename=_filenames,
    media_id=_media_ids,
    issue_id=_ids,
    tenant_id=_ids,
    severity=st.sampled_from(list(Severity)),
    description=st.text(min_size=1, max_size=80).filter(lambda s: s.strip() != ""),
    page_url=st.text(min_size=1, max_size=60).filter(lambda s: s.strip() != ""),
    element_mode=_element_modes,
    existing_alt=st.sampled_from([None, "", "   "]),
)
def test_property_22_resolvable_alt_text_yields_valid_auto_applicable_fix(
    filename: str,
    media_id: int,
    issue_id: str,
    tenant_id: str,
    severity: Severity,
    description: str,
    page_url: str,
    element_mode: str,
    existing_alt: str | None,
) -> None:
    """For any resolvable missing-alt-text Issue, ``generate_fix`` returns an
    auto-applicable ``update_alt_text`` SuggestedFix targeting the image's
    media_id, with non-empty heuristic alt text (<= 125 chars) explicitly labeled
    a placeholder heuristic (not AI-generated).

    Feature: website-orchestrator-milestone-0, Property 22: Resolvable
    missing-alt-text yields a valid auto-applicable fix

    Validates: Requirements 5.3, 5.4
    """
    # The single, genuinely resolvable image: has a media_id, a non-blank
    # filename, and is missing alt text.
    image = ImageRef(media_id=media_id, filename=filename, alt_text=existing_alt)

    # Vary how the issue points at the image; each mode still resolves to it.
    if element_mode == _ELEMENT_MODE_MEDIA_ID:
        element: str | None = f"<img> media_id={media_id}"
    elif element_mode == _ELEMENT_MODE_FILENAME:
        element = f"image element referencing {filename}"
    elif element_mode == _ELEMENT_MODE_UNRELATED:
        element = "some unrelated selector body > figure img"
    else:  # _ELEMENT_MODE_NONE
        element = None

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
        images=[image],
        crawled_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )

    fix = FixGenerator().generate_fix(issue, page)

    # A fix must be produced (never None for a resolvable missing-alt-text issue).
    assert fix is not None

    # Req 5.3 — auto-applicable update_alt_text fix targeting the image media_id.
    assert fix.auto_applicable == 1
    assert fix.fix_type == FixType.UPDATE_ALT_TEXT
    assert fix.target_ref is not None
    assert fix.target_ref.media_id == media_id

    # Req 5.3 — non-empty heuristic alt text of at most MAX_ALT_TEXT_LEN chars.
    assert fix.proposed_value is not None
    assert fix.proposed_value != ""
    assert 0 < len(fix.proposed_value) <= MAX_ALT_TEXT_LEN

    # Provenance / lifecycle: retains the originating Issue and tenant, pending.
    assert fix.issue_id == issue.id
    assert fix.tenant_id == issue.tenant_id
    assert fix.status == FixStatus.PENDING

    # Req 5.4 — alt text is labeled a placeholder heuristic, not AI-generated.
    assert fix.reason is not None
    reason_lower = fix.reason.lower()
    assert "heuristic" in reason_lower
    assert "not ai-generated" in reason_lower
