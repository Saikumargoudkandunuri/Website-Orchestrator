"""Technical SEO checks: links (broken, redirects, orphan pages)."""

from __future__ import annotations

from engines.technical_seo.models import FindingSeverity, TechnicalFinding


def check_broken_links(ko: object) -> TechnicalFinding:
    internal_seo = getattr(ko, "internal_seo", None)
    broken = getattr(internal_seo, "broken_links", []) if internal_seo else []
    if broken:
        return TechnicalFinding(
            check_name="broken_links",
            severity=FindingSeverity.HIGH,
            passed=False,
            description=f"{len(broken)} broken link(s) found on this page.",
            evidence=", ".join(b.url for b in broken[:3]),
            source="observed",
        )
    return TechnicalFinding(
        check_name="broken_links", severity=FindingSeverity.INFO,
        passed=True, description="No broken links detected.", source="observed",
    )


def check_redirect_chain(ko: object) -> TechnicalFinding:
    tech = getattr(ko, "technical_seo", None)
    chain = getattr(tech, "redirect_chain", []) if tech else []
    if len(chain) >= 3:
        return TechnicalFinding(
            check_name="redirect_chain",
            severity=FindingSeverity.MEDIUM,
            passed=False,
            description=f"Redirect chain has {len(chain)} hops (threshold: 3).",
            evidence=" → ".join(h.url for h in chain[:5]),
            source="observed",
        )
    return TechnicalFinding(
        check_name="redirect_chain", severity=FindingSeverity.INFO,
        passed=True, description="No excessive redirect chain.", source="observed",
    )


def check_orphan_page(ko: object) -> TechnicalFinding:
    internal_seo = getattr(ko, "internal_seo", None)
    is_orphan = getattr(internal_seo, "orphan_page", False) if internal_seo else False
    if is_orphan:
        return TechnicalFinding(
            check_name="orphan_page",
            severity=FindingSeverity.HIGH,
            passed=False,
            description="Page has no internal links pointing to it (orphan page).",
            source="inferred",
        )
    return TechnicalFinding(
        check_name="orphan_page", severity=FindingSeverity.INFO,
        passed=True, description="Page has internal links.", source="inferred",
    )


def check_link_depth(ko: object) -> TechnicalFinding:
    internal_seo = getattr(ko, "internal_seo", None)
    depth = getattr(internal_seo, "link_depth", None) if internal_seo else None
    if depth is not None and depth > 4:
        return TechnicalFinding(
            check_name="link_depth",
            severity=FindingSeverity.MEDIUM,
            passed=False,
            description=f"Page is {depth} clicks from homepage (recommended ≤ 4).",
            evidence=str(depth),
            source="observed",
        )
    return TechnicalFinding(
        check_name="link_depth", severity=FindingSeverity.INFO,
        passed=True,
        description=f"Link depth {depth} is within recommended range." if depth is not None else "Link depth not measured.",
        evidence=str(depth) if depth is not None else None,
        source="observed",
    )
