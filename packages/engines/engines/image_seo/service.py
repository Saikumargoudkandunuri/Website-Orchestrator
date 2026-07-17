"""Image SEO Engine service — pure computation over real, live page HTML.

Detection rules (deterministic, from real observed markup only):

* ``<img>`` with no ``alt`` attribute or an empty ``alt`` -> missing_alt
  (finding only; the executable fix is the existing alt-text governed path).
* ``src`` filename matches a generic camera/CMS pattern (``img123.jpg``,
  ``dsc0001.jpg``, ``image-1.png``, ``untitled.jpeg``, pure digits) -> poor_filename
  (finding only — renaming a live asset is out of scope for a content edit).
* Image not wrapped in ``<figure>``/no adjacent ``<figcaption>`` -> missing_caption.
* No ``loading`` attribute on an image beyond the first (first image is treated
  as a likely above-the-fold/LCP candidate and intentionally left eager) ->
  missing_lazy_loading.
* No ``width``/``height`` attributes -> missing_dimensions (real CLS risk).
"""
from __future__ import annotations

import re
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

from engines.image_seo.models import ImageFinding, ImageProposal, ImageSeoReport

__all__ = ["ImageSeoService"]

_POOR_FILENAME_PATTERNS = (
    re.compile(r"^img[-_]?\d+$", re.IGNORECASE),
    re.compile(r"^dsc[-_]?\d+$", re.IGNORECASE),
    re.compile(r"^image[-_]?\d*$", re.IGNORECASE),
    re.compile(r"^photo[-_]?\d*$", re.IGNORECASE),
    re.compile(r"^untitled.*$", re.IGNORECASE),
    re.compile(r"^\d+$"),
)


def _stem(src: str) -> str:
    path = urlsplit(src).path
    name = path.rsplit("/", 1)[-1]
    return name.rsplit(".", 1)[0] if "." in name else name


class ImageSeoService:
    engine_name = "image_seo"
    engine_version = "1.0.0"

    def analyze(self, page_url: str, html: str) -> ImageSeoReport:
        report = ImageSeoReport(page_url=page_url)
        if not html:
            report.notes.append("No live page content available.")
            report.provenance = "no_data"
            return report

        soup = BeautifulSoup(html, "html.parser")
        images = soup.find_all("img")
        report.images_analyzed = len(images)
        if not images:
            report.notes.append("No <img> elements found on this page.")
            return report

        for index, img in enumerate(images):
            src = img.get("src") or ""
            if not src:
                continue
            alt = img.get("alt")
            if alt is None or not alt.strip():
                report.findings.append(ImageFinding(
                    page_url=page_url, src=src, finding_type="missing_alt", severity="high",
                    evidence="no alt attribute or empty alt",
                ))

            stem = _stem(src)
            if any(pattern.match(stem) for pattern in _POOR_FILENAME_PATTERNS):
                report.findings.append(ImageFinding(
                    page_url=page_url, src=src, finding_type="poor_filename", severity="low",
                    evidence=f"filename stem {stem!r} matches a generic/non-descriptive pattern",
                ))

            parent = img.find_parent("figure")
            has_caption = bool(parent and parent.find("figcaption"))
            if not has_caption:
                report.findings.append(ImageFinding(
                    page_url=page_url, src=src, finding_type="missing_caption", severity="low",
                    evidence="image is not wrapped in a <figure> with a <figcaption>",
                ))
                report.proposals.append(ImageProposal(
                    page_url=page_url, src=src, finding_type="missing_caption",
                    caption=img.get("alt") or "",
                    reason="Wrap the image in a figure/figcaption for context and accessibility.",
                ))

            if index > 0 and not img.get("loading"):
                report.findings.append(ImageFinding(
                    page_url=page_url, src=src, finding_type="missing_lazy_loading", severity="medium",
                    evidence=f"image #{index + 1} has no loading attribute",
                ))
                report.proposals.append(ImageProposal(
                    page_url=page_url, src=src, finding_type="missing_lazy_loading",
                    loading="lazy",
                    reason="Below-the-fold image has no loading=lazy; add it to reduce initial page weight.",
                ))

            if not img.get("width") or not img.get("height"):
                report.findings.append(ImageFinding(
                    page_url=page_url, src=src, finding_type="missing_dimensions", severity="medium",
                    evidence="image has no explicit width/height attributes",
                ))

        if not report.findings:
            report.notes.append("No image-markup deficiencies detected on this page.")
        report.notes.append(
            "missing_alt findings are resolved through the existing alt-text governed "
            "fix path, not through a new structural edit."
        )
        return report
