"""Tests for SEO Tools reference phases 2-6 (Keyword, Rank, Backlink, Content, Competitor, AI Visibility)."""
from __future__ import annotations

from types import SimpleNamespace
from datetime import datetime, timezone

from engines.keyword_intelligence.services import KeywordIntelligenceService
from engines.keyword_intelligence.models import KeywordEngineReport
from engines.backlink_intelligence.services import BacklinkIntelligenceService
from engines.backlink_intelligence.models import (
    BacklinkIntelligenceReport, BacklinkRecord, DisavowEntry, ToxicLinkFlag,
)
from engines.content_intelligence.services import ContentIntelligenceService
from engines.content_intelligence.models import ContentBrief, FreshnessStatus
from engines.competitor_intelligence.services import CompetitorIntelligenceService
from engines.competitor_intelligence.models import CompetitorIntelligenceReport
from engines.ai_visibility.services import AiVisibilityService
from engines.ai_visibility.models import AiMention, AiVisibilityReport


# --- Priority 2: Keyword Intelligence ---------------------------------------

def test_keyword_gap_analysis_segments() -> None:
    ctx = SimpleNamespace(
        pages=[SimpleNamespace(page_id="p1", focus_keyphrase="seo tools")],
        competitor_keywords=[
            SimpleNamespace(keyword="seo audit", our_position=None, competitor_position=2, estimated_volume=1000),
            SimpleNamespace(keyword="seo tools", our_position=5, competitor_position=3, estimated_volume=2000),
            SimpleNamespace(keyword="rank tracker", our_position=1, competitor_position=4, estimated_volume=800),
        ],
    )
    svc = KeywordIntelligenceService()
    report = svc.analyze("p1", "s1", site_context=ctx)
    assert isinstance(report, KeywordEngineReport)
    segments = {g.keyword: g.segment for g in report.keyword_gaps}
    assert segments["seo audit"] == "missing"
    assert segments["seo tools"] == "weak"
    assert segments["rank tracker"] == "strong"


def test_pillar_plan_built_from_clusters() -> None:
    kw = SimpleNamespace(
        primary_focus_keyphrase="seo",
        secondary_keyphrases=["seo tools", "seo audit"],
        related_semantic_keywords=["seo software"],
        keyword_variations=["best seo"],
        search_volume=500,
        serp_features=["featured_snippet"],
    )
    ko = SimpleNamespace(keyword_intelligence=kw, tenant_id="t1")
    svc = KeywordIntelligenceService()
    report = svc.analyze("p1", "s1", knowledge_object=ko)
    assert report.pillar_plan
    assert report.serp_features
    assert report.serp_features[0].feature_type == "featured_snippet"


# --- Priority 3: Backlink Monitoring ----------------------------------------

def _bl(source, target, tld=False, anchor="brand", da=50, link_type="dofollow"):
    url = f"https://spam{tld}.xyz/x" if tld else source
    return BacklinkRecord(source_url=url, target_url=target, anchor_text=anchor,
                          domain_authority=da, link_type=link_type)


def test_toxicity_scoring_and_disavow() -> None:
    bls = [_bl("https://good.com/a", "https://us.com/", da=60),
           _bl("", "https://us.com/", tld=True, anchor="buy cheap")]
    svc = BacklinkIntelligenceService(provider=_StubProvider(bls, []))
    report = svc.analyze("s1", options={"domain": "us.com"})
    assert isinstance(report, BacklinkIntelligenceReport)
    assert report.toxic_links
    toxic = [t for t in report.toxic_links if t.toxicity_band == "toxic"]
    assert toxic
    assert report.disavow_entries
    assert report.disavow_entries[0].domain.endswith(".xyz")


def test_new_lost_backlink_detection() -> None:
    prev = [_bl("https://a.com/x", "https://us.com/")]
    curr = [_bl("https://a.com/x", "https://us.com/"), _bl("https://b.com/y", "https://us.com/")]
    svc = BacklinkIntelligenceService(provider=_StubProvider(curr, []))
    report = svc.analyze("s1", options={"domain": "us.com"}, previous_backlinks=prev)
    assert len(report.new_backlinks) == 1
    assert len(report.lost_backlinks) == 0


def test_render_disavow_file() -> None:
    entries = [DisavowEntry(domain="spam.xyz", reason="toxic")]
    text = BacklinkIntelligenceService.render_disavow_file(entries)
    assert "domain:spam.xyz" in text
    assert text.startswith("#")


class _StubProvider:
    def __init__(self, backlinks, referring):
        self._bl = backlinks
        self._rd = referring
    def name(self):
        return "stub"
    def fetch_backlinks(self, domain):
        from core.results import Ok
        return Ok(self._bl)
    def fetch_referring_domains(self, domain):
        from core.results import Ok
        return Ok(self._rd)


# --- Priority 4: Content Optimization ----------------------------------------

def test_content_brief_generation() -> None:
    svc = ContentIntelligenceService()
    brief = svc.generate_brief("seo audit", top_pages=[
        {"url": "https://a.com/1", "word_count": 2000},
        {"url": "https://b.com/2", "word_count": 1500},
    ], semantic_keywords=["crawl", "health score"])
    assert isinstance(brief, ContentBrief)
    assert brief.recommended_word_count == 1750
    assert "crawl" in brief.semantic_keywords
    assert brief.schema_suggestions


def test_freshness_stale_detection() -> None:
    old = datetime(2024, 1, 1, tzinfo=timezone.utc)
    ko = SimpleNamespace(content_intelligence=SimpleNamespace(last_updated=old), page_id="p1")
    svc = ContentIntelligenceService()
    fresh = svc._freshness(ko)
    assert isinstance(fresh, FreshnessStatus)
    assert fresh.is_stale is True
    assert fresh.days_since_update and fresh.days_since_update > 365


# --- Priority 5: Competitive Intelligence ------------------------------------

def test_competitor_comparison_and_backlink_gap() -> None:
    svc = CompetitorIntelligenceService()
    report = svc.analyze("s1", compare_domains=["rival.com", "other.com"])
    assert isinstance(report, CompetitorIntelligenceReport)
    assert report.comparison
    assert report.comparison[0].domain == "rival.com"
    # Backlink gap uses provider's competitor backlinks.
    assert isinstance(report.backlink_gaps, list)


# --- Priority 6: AI Visibility / GEO -----------------------------------------

def test_ai_visibility_share_of_voice_and_schema() -> None:
    mentions = [
        AiMention(query="best seo tool", platform="chatgpt", mentioned=True,
                  cited_url="https://us.com/guide"),
        AiMention(query="seo software", platform="perplexity", mentioned=False),
    ]
    ko = SimpleNamespace(schema_intelligence=SimpleNamespace(
        existing_schema=[{"@type": "Article"}], generated_jsonld=[]))
    svc = AiVisibilityService()
    report = svc.analyze("s1", knowledge_object=ko, mentions=mentions)
    assert isinstance(report, AiVisibilityReport)
    assert report.share_of_voice == 0.5
    assert report.citation_sources
    assert report.schema_readiness.readiness_score == 0.4  # JSON-LD + Article present (2/5)
    assert "FAQ schema" in report.schema_readiness.gaps
