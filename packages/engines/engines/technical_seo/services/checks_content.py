"""Technical SEO checks: content quality, headings, images, schema."""

from __future__ import annotations

from engines.technical_seo.models import FindingSeverity, TechnicalFinding


def check_thin_content(ko: object) -> TechnicalFinding:
    content = getattr(ko, "content_intelligence", None)
    thin = getattr(content, "thin_content", False) if content else False
    word_count = getattr(content, "word_count", 0) if content else 0
    if thin:
        return TechnicalFinding(
            check_name="thin_content",
            severity=FindingSeverity.MEDIUM,
            passed=False,
            description=f"Thin content: {word_count} words (minimum 300).",
            evidence=str(word_count),
            related_fix_type=None,
            source="inferred",
        )
    return TechnicalFinding(
        check_name="thin_content", severity=FindingSeverity.INFO,
        passed=True, description=f"Adequate content: {word_count} words.", source="observed",
    )


def check_h1_present(ko: object) -> TechnicalFinding:
    content = getattr(ko, "content_intelligence", None)
    h1 = getattr(content, "h1_analysis", None) if content else None
    count = getattr(h1, "count", 0) if h1 else 0
    issues = getattr(h1, "issues", []) if h1 else []
    if count == 0:
        return TechnicalFinding(
            check_name="missing_h1",
            severity=FindingSeverity.HIGH,
            passed=False,
            description="Page has no H1 heading.",
            related_fix_type=None,
            source="observed",
        )
    if count > 1:
        return TechnicalFinding(
            check_name="multiple_h1",
            severity=FindingSeverity.MEDIUM,
            passed=False,
            description=f"Page has {count} H1 headings; exactly one is recommended.",
            evidence=str(count),
            source="observed",
        )
    return TechnicalFinding(
        check_name="missing_h1", severity=FindingSeverity.INFO,
        passed=True, description="Page has exactly one H1.", source="observed",
    )


def check_images_have_alt(ko: object) -> TechnicalFinding:
    images_section = getattr(ko, "image_intelligence", None)
    images = getattr(images_section, "images", []) if images_section else []
    missing = [i for i in images if not (i.current_alt_text or "").strip()]
    if missing:
        return TechnicalFinding(
            check_name="images_missing_alt",
            severity=FindingSeverity.MEDIUM,
            passed=False,
            description=f"{len(missing)} image(s) missing alt text.",
            evidence=", ".join(i.filename for i in missing[:3]),
            related_fix_type="update_alt_text",
            source="observed",
        )
    return TechnicalFinding(
        check_name="images_missing_alt", severity=FindingSeverity.INFO,
        passed=True, description="All images have alt text.", source="observed",
    )


def check_schema_present(ko: object) -> TechnicalFinding:
    schema = getattr(ko, "schema_intelligence", None)
    existing = getattr(schema, "existing_schema", []) if schema else []
    has_schema = getattr(getattr(ko, "technical_seo", None), "crawlable", True)
    page_has_schema = bool(existing) or (hasattr(ko, "technical_seo") and
                                          getattr(getattr(ko, "identity", None), "url", ""))
    # Use the has_schema flag from the Knowledge Object directly
    identity = getattr(ko, "identity", None)
    from_ko = False
    if hasattr(ko, "__class__") and hasattr(ko, "technical_seo"):
        from_ko = True

    # Simple check: existing_schema or generated_jsonld indicates schema
    generated = getattr(schema, "generated_jsonld", []) if schema else []
    has = bool(existing or generated)
    if not has:
        return TechnicalFinding(
            check_name="missing_schema",
            severity=FindingSeverity.LOW,
            passed=False,
            description="No structured data (schema.org JSON-LD) detected.",
            related_fix_type="update_schema",
            source="observed",
        )
    return TechnicalFinding(
        check_name="missing_schema", severity=FindingSeverity.INFO,
        passed=True, description="Structured data is present.", source="observed",
    )
