"""Technical SEO checks: duplicate content across URLs (§1.2 On-Page SEO).

Detects when a page's body content is duplicated on other URLs in the crawl
(canonicalization / near-duplicate issues) and when title/meta descriptions are
shared across multiple pages (already partially covered by metadata checks).
"""

from __future__ import annotations

from engines.technical_seo.models import FindingSeverity, TechnicalFinding


def check_duplicate_content(ko: object) -> TechnicalFinding:
    """Flag pages whose content is duplicated on other URLs (§1.2)."""
    content = getattr(ko, "content_intelligence", None)
    duplicate_of = getattr(content, "duplicate_of", []) if content else []
    if duplicate_of:
        return TechnicalFinding(
            check_name="duplicate_content",
            severity=FindingSeverity.MEDIUM,
            passed=False,
            description=f"Page content is duplicated on {len(duplicate_of)} other URL(s).",
            evidence=", ".join(duplicate_of[:3]),
            related_fix_type="consolidate_duplicate_content",
            source="inferred",
        )
    return TechnicalFinding(
        check_name="duplicate_content", severity=FindingSeverity.INFO, passed=True,
        description="No duplicate content detected for this page.", source="inferred",
    )


def check_duplicate_meta_description(ko: object) -> TechnicalFinding:
    """Flag pages sharing an identical meta description with other pages (§1.2)."""
    meta = getattr(ko, "metadata", None)
    desc = getattr(getattr(meta, "meta_description", None), "current_value", None) if meta else None
    dup_desc = getattr(getattr(ko, "technical_seo", None), "duplicate_meta_description_of", []) if ko else []
    if desc and dup_desc:
        return TechnicalFinding(
            check_name="duplicate_meta_description",
            severity=FindingSeverity.LOW,
            passed=False,
            description=f"Meta description is shared with {len(dup_desc)} other page(s).",
            evidence=", ".join(dup_desc[:3]),
            source="inferred",
        )
    return TechnicalFinding(
        check_name="duplicate_meta_description", severity=FindingSeverity.INFO, passed=True,
        description="Meta description is unique.", source="inferred",
    )
