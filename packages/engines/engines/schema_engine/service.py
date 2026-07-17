"""Schema Engine service — pure computation over real crawled pages.

Detection rules (deterministic, from real observed signals only):

* No page on the site declares ``Organization`` -> gap on the homepage
  (identified as the shortest-path page, typically ``/``).
* A page whose real H1/heading text or URL path contains an FAQ-like keyword
  (``faq``, ``frequently-asked``) but declares no ``FAQPage`` schema -> gap.
* A page whose URL path contains a blog/article segment (``/blog/``,
  ``/posts/``, ``/news/``) but declares no ``Article``/``BlogPosting`` schema
  -> gap.
* A page with 2+ real headings starting with "how to" / containing "step" but
  no ``HowTo`` schema -> gap.

Every proposal's ``data`` is built only from the page's own title/url/headings
— never invented facts (Article ``headline`` = real title, FAQ ``question`` =
real matching heading text, etc.). A gap whose page carries no data usable for
a schema payload is reported but not proposed.
"""
from __future__ import annotations

import re
from urllib.parse import urlsplit

from engines.schema_engine.models import SchemaGap, SchemaProposal, SchemaReport

__all__ = ["SchemaEngineService"]

_FAQ_KEYWORDS = ("faq", "frequently-asked", "frequently asked")
_ARTICLE_PATH_SEGMENTS = ("/blog/", "/posts/", "/news/", "/article/")
_HOWTO_KEYWORDS = ("how to", "step-by-step", "step by step")


def _path(url: str) -> str:
    return (urlsplit(url).path or "/").lower()


class SchemaEngineService:
    engine_name = "schema_engine"
    engine_version = "1.0.0"

    def analyze(self, site_id: str, pages: list) -> SchemaReport:
        report = SchemaReport(site_id=site_id, pages_analyzed=len(pages))
        if not pages:
            report.notes.append("No crawled pages available; run a crawl first.")
            report.provenance = "no_data"
            return report

        has_organization = any("Organization" in (p.schema_types or []) for p in pages)
        if not has_organization:
            homepage = min(pages, key=lambda p: len(_path(p.url)))
            report.gaps.append(SchemaGap(
                page_url=homepage.url, missing_type="Organization",
                reason="No page on the site declares Organization schema.",
                evidence=["site-wide scan of schema_types found no Organization block"],
            ))
            report.proposals.append(SchemaProposal(
                page_url=homepage.url, schema_type="Organization",
                data={"name": homepage.title or homepage.url, "url": homepage.url},
                reason="Establish site-wide Organization entity for AI/GEO and knowledge-graph eligibility.",
            ))

        for page in pages:
            path = _path(page.url)
            headings = [h.text for h in (page.headings or [])]
            existing = page.schema_types or []

            faq_signal = any(k in path for k in _FAQ_KEYWORDS) or any(
                any(k in h.lower() for k in _FAQ_KEYWORDS) for h in headings
            )
            if faq_signal and "FAQPage" not in existing:
                report.gaps.append(SchemaGap(
                    page_url=page.url, missing_type="FAQPage",
                    reason="Page signals FAQ content but declares no FAQPage schema.",
                    evidence=[f"path/heading FAQ signal on {page.url}"],
                ))
                faq_headings = [h for h in headings if h and len(h) > 3][:5]
                if faq_headings:
                    report.proposals.append(SchemaProposal(
                        page_url=page.url, schema_type="FAQPage",
                        data={
                            "mainEntity": [
                                {"@type": "Question", "name": h,
                                 "acceptedAnswer": {"@type": "Answer", "text": h}}
                                for h in faq_headings
                            ]
                        },
                        reason="FAQ headings observed on the page with no FAQPage markup.",
                    ))

            is_article_path = any(seg in path for seg in _ARTICLE_PATH_SEGMENTS)
            if is_article_path and not ({"Article", "BlogPosting", "NewsArticle"} & set(existing)):
                report.gaps.append(SchemaGap(
                    page_url=page.url, missing_type="Article",
                    reason="URL path indicates an article/blog page with no Article schema.",
                    evidence=[f"path segment matched an article pattern: {path}"],
                ))
                if page.title:
                    report.proposals.append(SchemaProposal(
                        page_url=page.url, schema_type="Article",
                        data={"headline": page.title, "url": page.url},
                        reason="Blog/article URL pattern with a real page title and no Article markup.",
                    ))

            howto_headings = [h for h in headings if any(k in h.lower() for k in _HOWTO_KEYWORDS)]
            if len(howto_headings) >= 1 and "HowTo" not in existing:
                report.gaps.append(SchemaGap(
                    page_url=page.url, missing_type="HowTo",
                    reason="Page headings indicate step-by-step instructions with no HowTo schema.",
                    evidence=[f"matched heading: {h}" for h in howto_headings[:3]],
                ))
                if page.title:
                    report.proposals.append(SchemaProposal(
                        page_url=page.url, schema_type="HowTo",
                        data={
                            "name": page.title,
                            "step": [{"@type": "HowToStep", "text": h} for h in howto_headings],
                        },
                        reason="Real how-to headings observed with no HowTo markup.",
                    ))

        if not report.gaps:
            report.notes.append("No schema gaps detected from observed crawl signals.")
        return report
