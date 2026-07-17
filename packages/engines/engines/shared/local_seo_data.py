"""Deterministic local SEO data synthesizer (no network).

Builds realistic :class:`~intelligence.models.knowledge_object.KnowledgeObject`
and :class:`~engines.shared.site_context.SiteContext` instances from simple
inputs (domain, keyword, competitor list) using seeded hashing so the same
input always yields the same output. This lets every SEO engine run end-to-end
against meaningful, stable local data instead of requiring a live crawl or a
paid third-party API.
"""
from __future__ import annotations

import hashlib
import random
from urllib.parse import urlparse

from engines.shared.site_context import LinkGraphEdge, PageSummary, SiteContext

__all__ = [
    "build_knowledge_object",
    "build_site_context",
    "seed_from_string",
]

# A small curated corpus of realistic keywords/phrases used to synthesize
# keyword_intelligence sections deterministically per domain/keyword.
_KEYWORD_POOL = [
    "wordpress", "seo", "plugin", "theme", "speed", "security", "backup",
    "cache", "ssl", "cms", "blog", "hosting", "tutorial", "guide", "best",
    "free", "optimization", "performance", "schema", "analytics", "migrate",
]
_INTENT_POOL = ["informational", "navigational", "commercial_investigation", "transactional"]
_ENTITIES = [
    ("WordPress", "org"), ("PHP", "product"), ("MySQL", "product"),
    ("Automattic", "org"), ("Gutenberg", "product"), ("REST API", "product"),
]
_SECTIONS = ["blog", "docs", "pricing", "about", "contact", "features", "support"]


def seed_from_string(value: str) -> random.Random:
    """Return a stable Random instance seeded from ``value``."""
    h = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return random.Random(int(h[:16], 16))


def _domain_root(domain: str) -> str:
    domain = domain.replace("https://", "").replace("http://", "").strip("/")
    if domain.startswith("www."):
        domain = domain[4:]
    return domain or "example.com"


def build_knowledge_object(domain: str, keyword: str = "", *, tenant_id: str = "demo-tenant") -> object:
    """Synthesize a KnowledgeObject for a single representative page."""
    from intelligence.models.content_intelligence import ContentIntelligenceSection
    from intelligence.models.identity import IdentitySection, PageType
    from intelligence.models.internal_seo import InternalSeoSection
    from intelligence.models.keyword_intelligence import (
        KeywordIntelligenceSection,
        NamedEntity,
        SearchIntent,
    )
    from intelligence.models.metadata_intelligence import (
        MetadataField,
        MetadataSection,
        RobotsDirective,
    )
    from intelligence.models.schema_intelligence import (
        SchemaBlock,
        SchemaIntelligenceSection,
    )
    from intelligence.models.technical_seo import (
        PerformanceSignals,
        TechnicalSeoSection,
    )
    from intelligence.models.knowledge_object import KnowledgeObject

    root = _domain_root(domain)
    page_url = f"https://{root}/"
    focus = keyword or f"{root.split('.')[0]} guide"
    rnd = seed_from_string(f"{root}:{focus}")

    # Keyword intelligence
    secondary = [w for w in _KEYWORD_POOL if w not in focus.lower()][: rnd.randint(3, 5)]
    semantic = [f"{focus} {w}" for w in secondary[:3]]
    kw_section = KeywordIntelligenceSection(
        primary_focus_keyphrase=focus,
        secondary_keyphrases=secondary,
        related_semantic_keywords=semantic,
        named_entities=[__mk_entity(e) for e in _ENTITIES],
        search_intent=SearchIntent(_INTENT_POOL[rnd.randint(0, len(_INTENT_POOL) - 1)]),
        keyword_density={focus: round(rnd.uniform(0.5, 2.5), 2)},
        keyword_variations=[f"best {focus}", f"{focus} tutorial", f"free {focus}"],
        source="mixed",
    )

    # Content intelligence
    word_count = rnd.randint(600, 2600)
    headings = [f"Introduction to {focus}", f"Why {focus} matters", f"How to {focus}", "FAQ", "Conclusion"]
    content_section = ContentIntelligenceSection(
        word_count=word_count,
        readability_score=round(rnd.uniform(45, 92), 1),
        heading_structure=[{"level": 2, "text": h, "element_id": f"h-{i}"} for i, h in enumerate(headings)],
        first_paragraph=(
            f"This complete guide to {focus} covers everything you need to know, "
            "from the fundamentals through advanced techniques used by professionals."
        ),
        last_paragraph=(
            f"Now you have a solid understanding of {focus}. Apply these practices "
            "to improve your results and revisit this guide as the landscape evolves."
        ),
        topic_coverage_score=round(rnd.uniform(0.5, 0.95), 2),
        semantic_completeness_score=round(rnd.uniform(0.5, 0.95), 2),
    )

    # Identity
    identity = IdentitySection(
        url=page_url,
        canonical_url=page_url,
        page_type=PageType.HOME,
        language="en",
        slug="",
    )

    # Metadata
    metadata = MetadataSection(
        seo_title=MetadataField(current_value=f"{focus.title()} | {root.title()}"),
        meta_description=MetadataField(
            current_value=f"Learn everything about {focus} with our complete, up-to-date guide."
        ),
        canonical=MetadataField(current_value=page_url),
        robots=RobotsDirective(index=True, follow=True),
    )

    # Technical SEO
    tech = TechnicalSeoSection(
        crawlable=True,
        indexable=True,
        broken=False,
        performance_signals=PerformanceSignals(
            ttfb_ms=round(rnd.uniform(80, 900), 1),
            page_weight_bytes=rnd.randint(400_000, 3_500_000),
        ),
    )

    # Internal SEO
    internal = InternalSeoSection()

    # Schema
    has_schema = rnd.random() > 0.4
    schema = SchemaIntelligenceSection(
        existing_schema=(
            [SchemaBlock(type="WebSite", raw_jsonld='{"@type":"WebSite"}', element_id="ld1")]
            if has_schema else []
        ),
        generated_jsonld=[],
    )

    return KnowledgeObject(
        id=f"ko_{root.replace('.', '_')}",
        page_id=f"page_{root.replace('.', '_')}",
        site_id=root,
        tenant_id=tenant_id,
        version=1,
        identity=identity,
        metadata=metadata,
        keyword_intelligence=kw_section,
        content_intelligence=content_section,
        technical_seo=tech,
        internal_seo=internal,
        schema_intelligence=schema,
    )


def __mk_entity(e):
    from intelligence.models.keyword_intelligence import NamedEntity
    return NamedEntity(text=e[0], type=e[1], confidence=round(0.6 + (hash(e[0]) % 30) / 100, 2))


def build_site_context(domain: str, *, tenant_id: str = "demo-tenant", num_pages: int = 12) -> SiteContext:
    """Synthesize a SiteContext with a realistic page graph for ``domain``."""
    root = _domain_root(domain)
    rnd = seed_from_string(f"site:{root}")
    pages: list[PageSummary] = []
    edges: list[LinkGraphEdge] = []
    home_id = f"page_{root.replace('.', '_')}_home"

    for i in range(num_pages):
        if i == 0:
            pid = home_id
            url = f"https://{root}/"
            title = f"{root.title()} — Home"
            focus = root.split(".")[0]
            depth = 0
        else:
            section = _SECTIONS[(i - 1) % len(_SECTIONS)]
            pid = f"page_{root.replace('.', '_')}_{i}"
            url = f"https://{root}/{section}/"
            title = f"{section.title()} — {root.title()}"
            focus = f"{section} {root.split('.')[0]}"
            depth = 1 if i <= 6 else 2
        pages.append(PageSummary(
            page_id=pid,
            url=url,
            title=title,
            slug=urlparse(url).path,
            word_count=rnd.randint(400, 2200),
            focus_keyphrase=focus if rnd.random() > 0.2 else None,
            depth=depth,
            has_schema=rnd.random() > 0.5,
            broken=(i == num_pages - 1 and rnd.random() > 0.7),
        ))
        if i > 0:
            edges.append(LinkGraphEdge(from_page_id=home_id, to_page_id=pid, anchor_text=focus))

    return SiteContext(
        site_id=root,
        tenant_id=tenant_id,
        crawl_id=f"crawl_{root.replace('.', '_')}",
        pages=pages,
        link_graph=edges,
    )
