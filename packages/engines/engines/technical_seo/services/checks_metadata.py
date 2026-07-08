"""Technical SEO checks: metadata (title, meta description, canonical, robots)."""

from __future__ import annotations

from engines.technical_seo.models import FindingSeverity, TechnicalFinding


def check_missing_title(ko: object) -> TechnicalFinding:
    current = getattr(getattr(ko, "metadata", None), "seo_title", None)
    val = getattr(current, "current_value", None) if current else None
    return TechnicalFinding(
        check_name="missing_title",
        severity=FindingSeverity.HIGH,
        passed=bool(val and val.strip()),
        description="Page has no SEO title." if not val else "SEO title present.",
        evidence=val,
        related_fix_type="update_title",
        source="observed",
    )


def check_missing_meta_description(ko: object) -> TechnicalFinding:
    current = getattr(getattr(ko, "metadata", None), "meta_description", None)
    val = getattr(current, "current_value", None) if current else None
    return TechnicalFinding(
        check_name="missing_meta_description",
        severity=FindingSeverity.MEDIUM,
        passed=bool(val and val.strip()),
        description="Missing meta description." if not val else "Meta description present.",
        evidence=val,
        related_fix_type="update_meta_description",
        source="observed",
    )


def check_canonical_issues(ko: object) -> list[TechnicalFinding]:
    findings: list[TechnicalFinding] = []
    tech = getattr(ko, "technical_seo", None)
    for issue in getattr(tech, "canonical_issues", []):
        findings.append(TechnicalFinding(
            check_name="canonical_issue",
            severity=FindingSeverity.HIGH,
            passed=False,
            description=issue,
            source="inferred",
        ))
    if not findings:
        findings.append(TechnicalFinding(
            check_name="canonical_issue", severity=FindingSeverity.INFO,
            passed=True, description="No canonical issues detected.", source="inferred",
        ))
    return findings


def check_robots_directive(ko: object) -> TechnicalFinding:
    meta = getattr(ko, "metadata", None)
    robots = getattr(meta, "robots", None) if meta else None
    index = getattr(robots, "index", True) if robots else True
    follow = getattr(robots, "follow", True) if robots else True
    raw = getattr(robots, "raw", None) if robots else None
    if not index:
        return TechnicalFinding(
            check_name="robots_noindex",
            severity=FindingSeverity.CRITICAL,
            passed=False,
            description="Page is set to noindex — it will not appear in search results.",
            evidence=raw,
            source="observed",
        )
    return TechnicalFinding(
        check_name="robots_noindex", severity=FindingSeverity.INFO,
        passed=True, description="Page is indexable per robots directive.", evidence=raw,
        source="observed",
    )


def check_duplicate_title(ko: object) -> TechnicalFinding:
    tech = getattr(ko, "technical_seo", None)
    dups = getattr(tech, "duplicate_title_of", []) if tech else []
    if dups:
        return TechnicalFinding(
            check_name="duplicate_title",
            severity=FindingSeverity.MEDIUM,
            passed=False,
            description=f"Title duplicated on {len(dups)} other page(s).",
            evidence=", ".join(dups[:3]),
            source="observed",
        )
    return TechnicalFinding(
        check_name="duplicate_title", severity=FindingSeverity.INFO,
        passed=True, description="Title is unique.", source="observed",
    )


def check_duplicate_meta(ko: object) -> TechnicalFinding:
    tech = getattr(ko, "technical_seo", None)
    dups = getattr(tech, "duplicate_meta_of", []) if tech else []
    if dups:
        return TechnicalFinding(
            check_name="duplicate_meta_description",
            severity=FindingSeverity.MEDIUM,
            passed=False,
            description=f"Meta description duplicated on {len(dups)} other page(s).",
            evidence=", ".join(dups[:3]),
            source="observed",
        )
    return TechnicalFinding(
        check_name="duplicate_meta_description", severity=FindingSeverity.INFO,
        passed=True, description="Meta description is unique.", source="observed",
    )
