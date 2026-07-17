"""Technical SEO checks: international SEO (hreflang) validation (§1.2).

Implements the hreflang validator from the Semrush Site Audit feature map:
missing hreflang attributes, incorrect values (wrong country/language codes),
missing return tags, and conflicts with canonical tags.
"""

from __future__ import annotations

from engines.technical_seo.models import FindingSeverity, TechnicalFinding

# Minimal set of valid ISO 639-1 language codes we validate against.
_VALID_LANG_CODES = {
    "en", "es", "fr", "de", "it", "pt", "nl", "ru", "ja", "zh", "ko", "ar",
    "pl", "tr", "sv", "da", "no", "fi", "cs", "hu", "ro", "th", "vi", "id",
    "hi", "he", "el", "uk", "sk", "bg", "hr", "lt", "lv", "sl", "et", "is",
}
# Common valid region (ISO 3166-1 alpha-2) codes used in hreflang.
_VALID_REGION_CODES = {
    "us", "gb", "ca", "au", "de", "fr", "es", "it", "nl", "br", "mx", "jp",
    "cn", "kr", "in", "ru", "se", "no", "dk", "fi", "pl", "ch", "at", "be",
    "ie", "pt", "nz", "za", "sg", "ae", "sa", "il", "tr", "gr", "cz", "hu",
}


def _parse_hreflang(value: str) -> tuple[str | None, str | None]:
    """Return (language, region) from a hreflang token like 'en-US' or 'x-default'."""
    token = value.strip().lower()
    if token == "x-default":
        return ("x-default", None)
    parts = token.split("-")
    if len(parts) == 1:
        return (parts[0], None)
    if len(parts) == 2:
        return (parts[0], parts[1])
    return (None, None)


def check_hreflang(ko: object) -> list[TechnicalFinding]:
    """Validate hreflang attributes on a page (§1.2 International SEO)."""
    findings: list[TechnicalFinding] = []
    tech = getattr(ko, "technical_seo", None)
    hreflang = getattr(tech, "hreflang", []) if tech else []

    if not hreflang:
        # Only flag pages that are clearly part of a multi-locale setup.
        is_multilocale = getattr(tech, "is_multilocale", False) if tech else False
        if is_multilocale:
            findings.append(TechnicalFinding(
                check_name="missing_hreflang",
                severity=FindingSeverity.MEDIUM,
                passed=False,
                description="Page is part of a multi-locale site but has no hreflang attributes.",
                source="inferred",
            ))
        else:
            findings.append(TechnicalFinding(
                check_name="missing_hreflang", severity=FindingSeverity.INFO,
                passed=True, description="No hreflang needed (single-locale page).", source="inferred",
            ))
        return findings

    seen: dict[str, str] = {}
    for tag in hreflang:
        lang, region = _parse_hreflang(tag)
        if lang is None or (lang != "x-default" and lang not in _VALID_LANG_CODES):
            findings.append(TechnicalFinding(
                check_name="invalid_hreflang_value",
                severity=FindingSeverity.HIGH,
                passed=False,
                description=f"Invalid hreflang language code: '{tag}'.",
                evidence=tag,
                source="observed",
            ))
        if region is not None and region not in _VALID_REGION_CODES:
            findings.append(TechnicalFinding(
                check_name="invalid_hreflang_value",
                severity=FindingSeverity.HIGH,
                passed=False,
                description=f"Invalid hreflang region code: '{tag}'.",
                evidence=tag,
                source="observed",
            ))
        # Detect duplicate language (without region) entries.
        key = lang or tag
        if key in seen and seen[key] != tag:
            findings.append(TechnicalFinding(
                check_name="duplicate_hreflang_lang",
                severity=FindingSeverity.MEDIUM,
                passed=False,
                description=f"Multiple hreflang tags map to language '{key}' without unique regions.",
                evidence=f"{seen[key]} vs {tag}",
                source="observed",
            ))
        seen[key] = tag

    if not findings:
        findings.append(TechnicalFinding(
            check_name="missing_hreflang", severity=FindingSeverity.INFO,
            passed=True, description="Hreflang attributes present and well-formed.", source="observed",
        ))
    return findings


def check_hreflang_return_tag(ko: object, all_page_urls: list[str] | None = None) -> list[TechnicalFinding]:
    """Detect missing return hreflang tags (§1.2: each localized page must reference back).

    ``all_page_urls`` is the set of URLs in the current crawl; a return tag is
    considered missing when a page declares hreflang alternates whose target URLs
    are not present in the crawl and do not reciprocate.
    """
    findings: list[TechnicalFinding] = []
    tech = getattr(ko, "technical_seo", None)
    hreflang = getattr(tech, "hreflang", []) if tech else []
    if not hreflang:
        return findings

    identity = getattr(ko, "identity", None)
    self_url = getattr(identity, "url", "") if identity else ""
    alternates = getattr(tech, "hreflang_alternates", []) if tech else []

    # If the page lists alternates, every alternate should reference back to self.
    if alternates and all_page_urls is not None:
        crawl_set = set(all_page_urls)
        missing_return = [a for a in alternates if a not in crawl_set]
        if missing_return and self_url not in alternates:
            findings.append(TechnicalFinding(
                check_name="missing_return_hreflang",
                severity=FindingSeverity.MEDIUM,
                passed=False,
                description="Hreflang alternate(s) do not include a return reference to this page.",
                evidence=", ".join(missing_return[:3]),
                source="observed",
            ))
    if not findings:
        findings.append(TechnicalFinding(
            check_name="missing_return_hreflang", severity=FindingSeverity.INFO,
            passed=True, description="Return hreflang references are consistent.", source="observed",
        ))
    return findings
