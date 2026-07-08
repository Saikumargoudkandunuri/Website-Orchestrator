"""Technical SEO + Identity URL analysis (§4.10, §13.2). Deterministic.

Purely observed/computed — no AI. Populates the technical SEO section and the
identity URL analysis directly from the crawled page.
"""

from __future__ import annotations

from urllib.parse import urlsplit

from intelligence.models.identity import UrlAnalysis
from intelligence.models.technical_seo import RedirectHop, TechnicalSeoSection
from intelligence.services.base import AnalysisContext, AnalyzerService

__all__ = ["TechnicalSeoService"]

_STOP_WORDS = frozenset("a an the and or of to in for with on at by".split())


class TechnicalSeoService(AnalyzerService):
    section = "technical_seo"

    def analyze(self, ctx: AnalysisContext) -> None:
        page = ctx.page
        status = page.status_code or 0
        broken = not (200 <= status < 400)
        hops = [RedirectHop(url=h) for h in page.redirect_chain.hops]

        ctx.ko.technical_seo = TechnicalSeoSection(
            crawlable=True,  # the crawler retrieved it
            indexable=200 <= status < 300 and page.final_url == page.url or 200 <= status < 300,
            redirect_chain=hops,
            canonical_issues=self._canonical_issues(ctx),
            duplicate_title_of=[],
            duplicate_meta_of=[],
            broken=broken,
            performance_signals=None,  # not measured this milestone
        )
        ctx.ko.identity.url_analysis = self._url_analysis(ctx)

    def _canonical_issues(self, ctx: AnalysisContext) -> list[str]:
        issues: list[str] = []
        canonical = ctx.ko.identity.canonical_url
        if canonical and canonical != ctx.page.url and canonical != ctx.page.final_url:
            issues.append(
                f"canonical URL ({canonical}) differs from the page URL"
            )
        return issues

    def _url_analysis(self, ctx: AnalysisContext) -> UrlAnalysis:
        url = ctx.page.url
        parts = urlsplit(url)
        path = parts.path or "/"
        segments = [s for s in path.split("/") if s]
        slug = ctx.ko.identity.slug
        focus = ctx.ko.keyword_intelligence.primary_focus_keyphrase or ""
        issues: list[str] = []
        contains_stop = any(w in _STOP_WORDS for w in slug.split("-"))
        readable = slug == slug.lower() and "_" not in slug and not parts.query
        if not readable:
            issues.append("URL is not clean (uppercase, underscores, or query noise)")
        if len(url) > 100:
            issues.append("URL is long (>100 chars)")
        return UrlAnalysis(
            length_characters=len(url),
            contains_focus_keyphrase=bool(focus) and self._slugify(focus) in slug,
            contains_stop_words=contains_stop,
            readable_structure=readable,
            depth=len(segments),
            issues=issues,
        )

    @staticmethod
    def _slugify(text: str) -> str:
        return "-".join(t for t in text.lower().split() if t)
