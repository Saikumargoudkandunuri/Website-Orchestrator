"""Page Lifecycle Engine — real decisions from real crawl/link/content data."""
from __future__ import annotations

from datetime import datetime, timezone

from core.types import CrawledPage, HeadingRef, LinkStatus
from engines.page_lifecycle import PageLifecycleService

NOW = datetime(2024, 1, 1, tzinfo=timezone.utc)


def _page(url, title=None, h1=None, word_count=500, links=None):
    return CrawledPage(
        url=url, final_url=url, status_code=200, title=title, word_count=word_count,
        headings=[HeadingRef(level=1, text=h1)] if h1 else [],
        links=links or [], crawled_at=NOW,
    )


def test_orphan_page_yields_edit_decision() -> None:
    home = _page("https://x.com/", "Home", "Welcome", links=[])
    orphan = _page("https://x.com/orphan", "Orphan", "Orphan Page")
    report = PageLifecycleService().analyze("x.com", [home, orphan])
    edits = [d for d in report.decisions if d.action == "edit" and d.page_url == orphan.url]
    assert edits and edits[0].evidence


def test_duplicate_title_yields_merge_decision() -> None:
    a = _page("https://x.com/a", "Best SEO Tips", "Best SEO Tips",
              links=[LinkStatus(url="https://x.com/b", reachable=True, status_code=200, is_internal=True)])
    b = _page("https://x.com/b", "Best SEO Tips", "Best SEO Tips",
              links=[LinkStatus(url="https://x.com/a", reachable=True, status_code=200, is_internal=True)])
    report = PageLifecycleService().analyze("x.com", [a, b])
    merges = [d for d in report.decisions if d.action == "merge"]
    assert merges
    assert merges[0].page_url in (a.url, b.url)
    assert merges[0].merge_into_url in (a.url, b.url)
    assert merges[0].page_url != merges[0].merge_into_url


def test_thin_isolated_page_yields_delete_decision() -> None:
    home = _page("https://x.com/", "Home", "Welcome", word_count=500)
    thin = _page("https://x.com/thin", "Thin", "Thin Page", word_count=50, links=[])
    report = PageLifecycleService().analyze("x.com", [home, thin])
    deletes = [d for d in report.decisions if d.action == "delete"]
    assert deletes and deletes[0].page_url == thin.url


def test_cluster_yields_pillar_and_expand_decisions() -> None:
    p1 = _page("https://x.com/seo-guide", "SEO Guide", "SEO Guide")
    p2 = _page("https://x.com/seo-tips", "SEO Tips", "SEO Tips")
    p3 = _page("https://x.com/seo-basics", "SEO Basics", "SEO Basics")
    cluster = {"cluster_id": "c1", "topic_label": "SEO", "member_page_ids": [p1.url, p2.url, p3.url]}
    report = PageLifecycleService().analyze("x.com", [p1, p2, p3], clusters=[cluster])
    actions = {d.action for d in report.decisions}
    assert "make_pillar" in actions or "expand_cluster" in actions


def test_missing_entity_yields_create_decision() -> None:
    home = _page("https://x.com/", "Home", "Welcome")
    report = PageLifecycleService().analyze("x.com", [home], missing_entities=["Local SEO"])
    creates = [d for d in report.decisions if d.action == "create"]
    assert creates and creates[0].proposed_url == "/local-seo"


def test_no_pages_is_honest_no_data() -> None:
    report = PageLifecycleService().analyze("x.com", [])
    assert report.provenance == "no_data"
    assert report.decisions == []
