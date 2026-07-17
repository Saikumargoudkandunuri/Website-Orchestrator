"""Milestone 5 — Automatic Blog Writer: production-ready HTML field coverage.

``GeneratedPage`` (api.ai_writer) is the RankMath-aligned record every AI
Writer V2 draft carries. These tests exercise the pure rendering/derivation
methods directly (no AI Gateway call, no network) to prove the page assembles
a complete, WordPress-ready HTML document: breadcrumb, table of contents,
internal + external links, FAQ, CTA, schema, and the separate RankMath/OG/
Twitter/canonical postmeta payload used by the governed ``UPDATE_SEO_META``
fix.
"""
from __future__ import annotations

from api.ai_writer import GeneratedPage, _default_breadcrumb


def _sample_page() -> GeneratedPage:
    page = GeneratedPage(
        focus_keyphrase="best hiking boots",
        seo_slug="best-hiking-boots",
        secondary_keywords=["waterproof boots", "trail boots"],
        meta_title="Best Hiking Boots 2026",
        meta_description="A complete guide to the best hiking boots.",
        title="Best Hiking Boots 2026",
        sections=[
            {"heading": "Why Boots Matter", "content": "Good boots protect your feet."},
            {"heading": "Top Picks", "content": "Here are our top picks."},
        ],
        faqs=[{"question": "How long do hiking boots last?", "answer": "2-3 years with care."}],
        schema_type="Article",
        schema_jsonld='{"@type": "Article"}',
        internal_links=[{"target_url": "https://example.com/gear", "suggested_anchor": "hiking gear guide"}],
        external_links=[{"url": "https://en.wikipedia.org/wiki/Hiking_boot", "anchor_text": "hiking boot (Wikipedia)"}],
        cta="Ready to find your next pair? Shop now.",
    )
    page.canonical_url = "https://example.com/best-hiking-boots"
    page.og_title = page.meta_title
    page.og_description = page.meta_description
    page.twitter_title = page.og_title
    page.twitter_description = page.og_description
    page.breadcrumb = _default_breadcrumb(page.canonical_url, page.title)
    return page


def test_default_breadcrumb_derives_real_path_segments() -> None:
    trail = _default_breadcrumb("https://example.com/guides/hiking/best-boots", "Best Boots")
    names = [c["name"] for c in trail]
    assert names[0] == "example.com"
    assert "Guides" in names
    assert "Hiking" in names
    assert names[-1] == "Best Boots"
    assert trail[-1]["url"] == "https://example.com/guides/hiking/best-boots"


def test_default_breadcrumb_empty_for_missing_host() -> None:
    assert _default_breadcrumb("", "Title") == []


def test_to_html_includes_every_required_section() -> None:
    page = _sample_page()
    html = page.to_html()

    assert "<h1>Best Hiking Boots 2026</h1>" in html
    assert 'class="table-of-contents"' in html
    assert 'id="why-boots-matter"' in html
    assert '<a href="#why-boots-matter">Why Boots Matter</a>' in html
    assert 'class="breadcrumb"' in html
    assert "hiking gear guide" in html  # internal link
    assert "en.wikipedia.org" in html and 'rel="noopener nofollow"' in html  # external authority link
    assert "Frequently Asked Questions" in html
    assert "How long do hiking boots last?" in html
    assert 'class="cta"' in html
    assert '"@type": "Article"' in html
    assert "BreadcrumbList" in html


def test_to_table_of_contents_html_empty_when_disabled() -> None:
    page = _sample_page()
    page.include_table_of_contents = False
    assert page.to_table_of_contents_html() == ""


def test_to_seo_meta_maps_rankmath_og_twitter_canonical_fields() -> None:
    page = _sample_page()
    meta = page.to_seo_meta()

    assert meta["rank_math_title"] == "Best Hiking Boots 2026"
    assert meta["rank_math_description"] == "A complete guide to the best hiking boots."
    assert meta["rank_math_focus_keyword"] == "best hiking boots"
    assert meta["rank_math_canonical_url"] == "https://example.com/best-hiking-boots"
    assert meta["rank_math_facebook_title"] == "Best Hiking Boots 2026"
    assert meta["rank_math_twitter_card_type"] == "summary_large_image"


def test_to_dict_includes_seo_meta_and_new_fields() -> None:
    page = _sample_page()
    data = page.to_dict()

    assert "seo_meta" in data
    assert data["seo_meta"]["rank_math_title"] == "Best Hiking Boots 2026"
    assert data["breadcrumb"][-1]["name"] == "Best Hiking Boots 2026"
    assert data["og_type"] == "article"
    assert data["twitter_card"] == "summary_large_image"
