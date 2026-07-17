"""Technical SEO checks: performance, Core Web Vitals, HTTPS security (§1.2).

Implements the Performance and HTTPS & Security categories from the Semrush
Site Audit feature map: Core Web Vitals (LCP, INP, CLS), TTFB, mixed content,
and insecure form actions.
"""

from __future__ import annotations

from engines.technical_seo.models import FindingSeverity, TechnicalFinding

# Core Web Vitals thresholds (Google "good" / "needs improvement" boundaries).
_LCP_GOOD = 2.5       # seconds
_LCP_POOR = 4.0
_INP_GOOD = 200.0    # milliseconds
_INP_POOR = 500.0
_CLS_GOOD = 0.1
_CLS_POOR = 0.25
_TTFB_GOOD = 0.8     # seconds
_TTFB_POOR = 1.8


def check_core_web_vitals(ko: object) -> list[TechnicalFinding]:
    """Validate Core Web Vitals (LCP, INP, CLS) from PageSpeed-style data (§1.2)."""
    findings: list[TechnicalFinding] = []
    perf = getattr(ko, "performance", None)
    cwv = getattr(perf, "core_web_vitals", None) if perf else None
    if cwv is None:
        findings.append(TechnicalFinding(
            check_name="core_web_vitals",
            severity=FindingSeverity.LOW,
            passed=True,
            description="Core Web Vitals not measured (no performance data supplied).",
            source="inferred",
        ))
        return findings

    lcp = getattr(cwv, "lcp", None)
    inp = getattr(cwv, "inp", None)
    cls = getattr(cwv, "cls", None)

    if lcp is not None:
        if lcp > _LCP_POOR:
            findings.append(TechnicalFinding(
                check_name="cwv_lcp_poor", severity=FindingSeverity.HIGH, passed=False,
                description=f"LCP is {lcp:.2f}s (poor; threshold {_LCP_POOR}s).",
                evidence=str(lcp), source="observed",
            ))
        elif lcp > _LCP_GOOD:
            findings.append(TechnicalFinding(
                check_name="cwv_lcp_ni", severity=FindingSeverity.MEDIUM, passed=False,
                description=f"LCP is {lcp:.2f}s (needs improvement; target {_LCP_GOOD}s).",
                evidence=str(lcp), source="observed",
            ))
        else:
            findings.append(TechnicalFinding(
                check_name="cwv_lcp_good", severity=FindingSeverity.INFO, passed=True,
                description=f"LCP is {lcp:.2f}s (good).", evidence=str(lcp), source="observed",
            ))

    if inp is not None:
        if inp > _INP_POOR:
            findings.append(TechnicalFinding(
                check_name="cwv_inp_poor", severity=FindingSeverity.HIGH, passed=False,
                description=f"INP is {inp:.0f}ms (poor; threshold {_INP_POOR:.0f}ms).",
                evidence=str(inp), source="observed",
            ))
        elif inp > _INP_GOOD:
            findings.append(TechnicalFinding(
                check_name="cwv_inp_ni", severity=FindingSeverity.MEDIUM, passed=False,
                description=f"INP is {inp:.0f}ms (needs improvement; target {_INP_GOOD:.0f}ms).",
                evidence=str(inp), source="observed",
            ))
        else:
            findings.append(TechnicalFinding(
                check_name="cwv_inp_good", severity=FindingSeverity.INFO, passed=True,
                description=f"INP is {inp:.0f}ms (good).", evidence=str(inp), source="observed",
            ))

    if cls is not None:
        if cls > _CLS_POOR:
            findings.append(TechnicalFinding(
                check_name="cwv_cls_poor", severity=FindingSeverity.HIGH, passed=False,
                description=f"CLS is {cls:.3f} (poor; threshold {_CLS_POOR}).",
                evidence=str(cls), source="observed",
            ))
        elif cls > _CLS_GOOD:
            findings.append(TechnicalFinding(
                check_name="cwv_cls_ni", severity=FindingSeverity.MEDIUM, passed=False,
                description=f"CLS is {cls:.3f} (needs improvement; target {_CLS_GOOD}).",
                evidence=str(cls), source="observed",
            ))
        else:
            findings.append(TechnicalFinding(
                check_name="cwv_cls_good", severity=FindingSeverity.INFO, passed=True,
                description=f"CLS is {cls:.3f} (good).", evidence=str(cls), source="observed",
            ))
    return findings


def check_ttfb(ko: object) -> TechnicalFinding:
    """Check Time To First Byte (§1.2 Performance)."""
    perf = getattr(ko, "performance", None)
    ttfb = getattr(perf, "ttfb", None) if perf else None
    if ttfb is None:
        return TechnicalFinding(
            check_name="ttfb", severity=FindingSeverity.LOW, passed=True,
            description="TTFB not measured.", source="inferred",
        )
    if ttfb > _TTFB_POOR:
        return TechnicalFinding(
            check_name="ttfb_poor", severity=FindingSeverity.MEDIUM, passed=False,
            description=f"TTFB is {ttfb:.2f}s (poor; threshold {_TTFB_POOR}s).",
            evidence=str(ttfb), source="observed",
        )
    if ttfb > _TTFB_GOOD:
        return TechnicalFinding(
            check_name="ttfb_ni", severity=FindingSeverity.LOW, passed=False,
            description=f"TTFB is {ttfb:.2f}s (needs improvement; target {_TTFB_GOOD}s).",
            evidence=str(ttfb), source="observed",
        )
    return TechnicalFinding(
        check_name="ttfb_good", severity=FindingSeverity.INFO, passed=True,
        description=f"TTFB is {ttfb:.2f}s (good).", evidence=str(ttfb), source="observed",
    )


def check_mixed_content(ko: object) -> TechnicalFinding:
    """Detect HTTPS page loading HTTP assets (§1.2 HTTPS & Security)."""
    perf = getattr(ko, "performance", None)
    mixed = getattr(perf, "mixed_content_urls", []) if perf else []
    if mixed:
        return TechnicalFinding(
            check_name="mixed_content",
            severity=FindingSeverity.HIGH,
            passed=False,
            description=f"{len(mixed)} HTTP asset(s) loaded on an HTTPS page (mixed content).",
            evidence=", ".join(mixed[:3]),
            source="observed",
        )
    return TechnicalFinding(
        check_name="mixed_content", severity=FindingSeverity.INFO, passed=True,
        description="No mixed content detected.", source="observed",
    )


def check_insecure_form_action(ko: object) -> TechnicalFinding:
    """Detect insecure (HTTP) form actions on a page (§1.2 HTTPS & Security)."""
    perf = getattr(ko, "performance", None)
    insecure_forms = getattr(perf, "insecure_form_actions", []) if perf else []
    if insecure_forms:
        return TechnicalFinding(
            check_name="insecure_form_action",
            severity=FindingSeverity.HIGH,
            passed=False,
            description=f"{len(insecure_forms)} form(s) submit to an insecure HTTP endpoint.",
            evidence=", ".join(insecure_forms[:3]),
            source="observed",
        )
    return TechnicalFinding(
        check_name="insecure_form_action", severity=FindingSeverity.INFO, passed=True,
        description="All form actions use secure endpoints.", source="observed",
    )
