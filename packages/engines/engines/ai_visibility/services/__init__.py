"""AI Visibility / GEO engine service (§1.9 / §2.6 / §5 P6)."""
from __future__ import annotations

from typing import Any

from engines.ai_visibility.models import (
    AiMention,
    AiVisibilityReport,
    CitationSource,
    SchemaReadiness,
)

__all__ = ["AiVisibilityService"]

_PLATFORMS = ("chatgpt", "perplexity", "gemini", "google_ai_overview")


class AiVisibilityService:
    """Computes AI search visibility and schema readiness for a site (§5 P6)."""

    def analyze(self, site_id: str, *, knowledge_object: Any = None,
                site_context: Any = None, options: dict | None = None,
                mentions: list[AiMention] | None = None) -> AiVisibilityReport:
        tenant_id = getattr(knowledge_object, "tenant_id", "") if knowledge_object else ""
        mentions = mentions or []
        sov = self._share_of_voice(mentions)
        citations = self._citation_sources(mentions)
        readiness = self._schema_readiness(knowledge_object)
        ai_traffic = (options or {}).get("ai_traffic_estimate")
        return AiVisibilityReport(
            site_id=site_id, tenant_id=tenant_id,
            mentions=mentions, share_of_voice=sov,
            citation_sources=citations, schema_readiness=readiness,
            ai_traffic_estimate=ai_traffic,
        )

    @staticmethod
    def _share_of_voice(mentions: list[AiMention]) -> float | None:
        """AI Share of Voice across tracked queries (§2.6)."""
        if not mentions:
            return None
        mentioned = sum(1 for m in mentions if m.mentioned)
        return round(mentioned / len(mentions), 3)

    @staticmethod
    def _citation_sources(mentions: list[AiMention]) -> list[CitationSource]:
        """Aggregate which URLs LLMs cite when mentioning the brand (§2.6)."""
        by_url: dict[str, CitationSource] = {}
        for m in mentions:
            if not m.cited_url:
                continue
            existing = by_url.get(m.cited_url)
            if existing is None:
                by_url[m.cited_url] = CitationSource(url=m.cited_url, citation_count=1)
            else:
                existing.citation_count += 1
        return list(by_url.values())

    @staticmethod
    def _schema_readiness(ko: Any) -> SchemaReadiness:
        """Assess schema completeness for LLM citation eligibility (§1.2 AI/GEO)."""
        gaps: list[str] = []
        has_jsonld = False
        has_article = False
        has_faq = False
        has_author = False
        has_org = False
        if ko is not None:
            schema = getattr(ko, "schema_intelligence", None)
            existing = getattr(schema, "existing_schema", []) if schema else []
            generated = getattr(schema, "generated_jsonld", []) if schema else []
            all_schema = list(existing) + list(generated)
            has_jsonld = bool(all_schema)
            joined = " ".join(str(s).lower() for s in all_schema)
            has_article = "article" in joined
            has_faq = "faq" in joined
            has_author = "author" in joined
            has_org = "organization" in joined
        for label, present in (
            ("JSON-LD present", has_jsonld),
            ("Article schema", has_article),
            ("FAQ schema", has_faq),
            ("Author bio", has_author),
            ("Organization schema", has_org),
        ):
            if not present:
                gaps.append(label)
        score = (5 - len(gaps)) / 5
        return SchemaReadiness(
            has_jsonld=has_jsonld, has_article_schema=has_article,
            has_faq_schema=has_faq, has_author_bio=has_author,
            has_organization_schema=has_org, readiness_score=score, gaps=gaps,
        )
