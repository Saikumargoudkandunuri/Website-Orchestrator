"""Technical SEO checks: crawlability, indexability, HTTPS, page status."""

from __future__ import annotations

from engines.technical_seo.models import FindingSeverity, TechnicalFinding


def check_broken_page(ko: object) -> TechnicalFinding:
    tech = getattr(ko, "technical_seo", None)
    broken = getattr(tech, "broken", False) if tech else False
    if broken:
        return TechnicalFinding(
            check_name="broken_page",
            severity=FindingSeverity.CRITICAL,
            passed=False,
            description="Page returned a non-2xx HTTP status.",
            related_fix_type=None,
            source="observed",
        )
    return TechnicalFinding(
        check_name="broken_page", severity=FindingSeverity.INFO,
        passed=True, description="Page returns a 2xx status.", source="observed",
    )


def check_indexability(ko: object) -> TechnicalFinding:
    tech = getattr(ko, "technical_seo", None)
    indexable = getattr(tech, "indexable", True) if tech else True
    if not indexable:
        return TechnicalFinding(
            check_name="not_indexable",
            severity=FindingSeverity.HIGH,
            passed=False,
            description="Page is not indexable (robots, noindex, or canonical issue).",
            source="observed",
        )
    return TechnicalFinding(
        check_name="not_indexable", severity=FindingSeverity.INFO,
        passed=True, description="Page is indexable.", source="observed",
    )


def check_https(ko: object) -> TechnicalFinding:
    identity = getattr(ko, "identity", None)
    url = getattr(identity, "url", "") if identity else ""
    is_https = url.lower().startswith("https://")
    if not is_https:
        return TechnicalFinding(
            check_name="not_https",
            severity=FindingSeverity.HIGH,
            passed=False,
            description="Page is not served over HTTPS.",
            evidence=url,
            source="observed",
        )
    return TechnicalFinding(
        check_name="not_https", severity=FindingSeverity.INFO,
        passed=True, description="Page served over HTTPS.", source="observed",
    )


def check_crawl_depth(ko: object, site_context: object | None = None) -> TechnicalFinding:
    identity = getattr(ko, "identity", None)
    url_analysis = getattr(identity, "url_analysis", None) if identity else None
    depth = getattr(url_analysis, "depth", None) if url_analysis else None
    if depth is not None and depth > 5:
        return TechnicalFinding(
            check_name="excessive_url_depth",
            severity=FindingSeverity.LOW,
            passed=False,
            description=f"URL has {depth} path segments (recommended ≤ 5).",
            evidence=str(depth),
            source="observed",
        )
    return TechnicalFinding(
        check_name="excessive_url_depth", severity=FindingSeverity.INFO,
        passed=True,
        description=f"URL depth {depth} is acceptable." if depth is not None else "URL depth not measured.",
        source="observed",
    )
