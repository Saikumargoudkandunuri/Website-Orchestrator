"""Image SEO Engine — real detection from live HTML (Milestone 5)."""
from __future__ import annotations

from engines.image_seo import ImageSeoService

HTML = """
<html><body>
<img src="https://cdn.example.com/img001.jpg">
<img src="https://cdn.example.com/hero-banner.jpg" alt="Hero banner" width="800" height="400" loading="lazy">
<img src="https://cdn.example.com/dsc0002.png" alt="team photo">
</body></html>
"""


def test_detects_missing_alt_and_poor_filename_and_dimensions() -> None:
    report = ImageSeoService().analyze("https://example.com/", HTML)
    assert report.images_analyzed == 3
    types = {f.finding_type for f in report.findings}
    assert "missing_alt" in types
    assert "poor_filename" in types
    assert "missing_dimensions" in types
    assert "missing_caption" in types


def test_first_image_exempt_from_lazy_loading_but_others_flagged() -> None:
    report = ImageSeoService().analyze("https://example.com/", HTML)
    lazy_findings = [f for f in report.findings if f.finding_type == "missing_lazy_loading"]
    srcs = {f.src for f in lazy_findings}
    assert "https://cdn.example.com/img001.jpg" not in srcs  # first image exempt
    assert "https://cdn.example.com/dsc0002.png" in srcs


def test_no_images_reports_honest_empty() -> None:
    report = ImageSeoService().analyze("https://example.com/", "<p>no images</p>")
    assert report.images_analyzed == 0
    assert report.findings == []
    assert report.notes


def test_no_html_is_honest_no_data() -> None:
    report = ImageSeoService().analyze("https://example.com/", "")
    assert report.provenance == "no_data"
    assert report.images_analyzed == 0


def test_proper_image_produces_no_findings() -> None:
    html = (
        '<figure><img src="https://cdn.example.com/hero-banner.jpg" '
        'alt="Hero banner for the homepage" width="800" height="400" loading="lazy">'
        "<figcaption>Hero banner</figcaption></figure>"
    )
    report = ImageSeoService().analyze("https://example.com/", html)
    assert report.images_analyzed == 1
    assert report.findings == []
