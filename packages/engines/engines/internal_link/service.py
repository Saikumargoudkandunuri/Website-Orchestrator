"""Internal Link Engine service — pure computation over real crawl pages.

Input is the list of actual crawled pages (``core.types.CrawledPage``) read from
the Digital Twin. No synthesized/fixture data is used: if the site has not been
crawled, the report is honestly empty.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlsplit

from engines.internal_link.models import (
    InternalLinkProposal,
    InternalLinkReport,
    PageAuthority,
)
from engines.site_architecture.services import SiteArchitectureService

__all__ = ["InternalLinkService"]

_WEAK_AUTHORITY = 0.20   # normalized PageRank below this is "weak"
_MAX_PROPOSALS = 50
_STOPWORDS = frozenset({
    "the", "and", "for", "with", "your", "our", "you", "are", "how", "what",
    "best", "top", "get", "www", "com", "net", "org", "html", "php", "page",
})


@dataclass(frozen=True)
class _Edge:
    from_page_id: str
    to_page_id: str


def _normalize(url: str) -> str:
    parts = urlsplit(url if "://" in url else f"https://{url}")
    host = (parts.hostname or "").lower().removeprefix("www.")
    path = (parts.path or "/").rstrip("/") or "/"
    return f"{host}{path}"


def _tokens(text: str) -> frozenset[str]:
    return frozenset(
        w for w in re.split(r"\W+", (text or "").lower())
        if len(w) > 2 and w not in _STOPWORDS
    )


def _slug(url: str) -> str:
    path = urlsplit(url).path.rstrip("/")
    return path.rsplit("/", 1)[-1] if path else ""


class InternalLinkService:
    """Analyze the real internal link graph and propose governed links."""

    engine_name = "internal_link"
    engine_version = "1.0.0"

    def analyze(self, site_id: str, pages: list) -> InternalLinkReport:
        report = InternalLinkReport(site_id=site_id, pages_analyzed=len(pages))
        if not pages:
            report.notes.append("No crawled pages available; run a crawl first.")
            report.provenance = "no_data"
            return report

        # Index pages by normalized URL (the stable node id for the graph).
        by_id: dict[str, object] = {}
        for page in pages:
            by_id[_normalize(page.url)] = page
        page_ids = set(by_id)

        # Resolve real outbound links to internal targets by URL match.
        edges: list[_Edge] = []
        inbound: dict[str, int] = {pid: 0 for pid in page_ids}
        outbound: dict[str, int] = {pid: 0 for pid in page_ids}
        existing: set[tuple[str, str]] = set()
        for pid, page in by_id.items():
            for link in getattr(page, "links", []) or []:
                target = _normalize(getattr(link, "url", ""))
                if target in page_ids and target != pid:
                    edges.append(_Edge(from_page_id=pid, to_page_id=target))
                    existing.add((pid, target))
                    outbound[pid] += 1
                    inbound[target] += 1

        # Reuse the Site Architecture PageRank (authority flow) — no duplication.
        scores = SiteArchitectureService()._pagerank(page_ids, edges)  # noqa: SLF001

        authorities = [
            PageAuthority(
                url=getattr(by_id[pid], "url", pid),
                title=getattr(by_id[pid], "title", None),
                authority_score=scores.get(pid, 0.0),
                inbound_internal_links=inbound[pid],
                outbound_internal_links=outbound[pid],
                is_orphan=inbound[pid] == 0,
            )
            for pid in page_ids
        ]
        authorities.sort(key=lambda a: a.authority_score, reverse=True)

        orphans = [a for a in authorities if a.is_orphan]
        weak = [a for a in authorities if not a.is_orphan and a.authority_score < _WEAK_AUTHORITY]

        report.internal_edges = len(edges)
        report.orphan_count = len(orphans)
        report.weak_page_count = len(weak)
        report.authorities = authorities
        report.structure_score = round(
            min(1.0, len(edges) / max(1, len(page_ids) * 3)), 4
        )
        report.proposals = self._propose(by_id, scores, orphans + weak, existing)
        if not report.proposals and (orphans or weak):
            report.notes.append(
                "Targets need equity but no topically-related source page was found; "
                "consider new supporting content."
            )
        report.notes.append(
            "Anchor text and WordPress page-id resolution are not captured by the "
            "crawler yet; proposals are governed recommendations, not auto-publish."
        )
        return report

    def _propose(self, by_id, scores, targets, existing) -> list[InternalLinkProposal]:
        # Precompute topical tokens per page from real title + slug.
        token_map = {
            pid: _tokens(f"{getattr(page, 'title', '') or ''} {_slug(getattr(page, 'url', ''))}")
            for pid, page in by_id.items()
        }
        ranked_sources = sorted(by_id, key=lambda pid: scores.get(pid, 0.0), reverse=True)
        proposals: list[InternalLinkProposal] = []
        for target in targets:
            target_id = _normalize(target.url)
            target_tokens = token_map.get(target_id, frozenset())
            best: tuple[float, str] | None = None
            for src_id in ranked_sources:
                if src_id == target_id or (src_id, target_id) in existing:
                    continue
                overlap = len(token_map.get(src_id, frozenset()) & target_tokens)
                if overlap == 0:
                    continue
                relevance = overlap + scores.get(src_id, 0.0)
                if best is None or relevance > best[0]:
                    best = (relevance, src_id)
            if best is None:
                continue
            src_id = best[1]
            source_page = by_id[src_id]
            anchor = (target.title or _slug(target.url) or "related page").strip()
            priority = "high" if target.is_orphan else "medium"
            proposals.append(
                InternalLinkProposal(
                    source_url=getattr(source_page, "url", src_id),
                    target_url=target.url,
                    suggested_anchor=anchor[:80],
                    reason=(
                        f"{'Orphan' if target.is_orphan else 'Low-authority'} page needs internal "
                        f"equity; link from a higher-authority topically-related page."
                    ),
                    evidence=[
                        f"target inbound internal links: {target.inbound_internal_links}",
                        f"target authority: {target.authority_score}",
                        f"source authority: {round(scores.get(src_id, 0.0), 4)}",
                        f"shared topic tokens with source: {len(token_map.get(src_id, frozenset()) & target_tokens)}",
                    ],
                    source_authority=round(scores.get(src_id, 0.0), 4),
                    target_authority=target.authority_score,
                    priority=priority,
                )
            )
            if len(proposals) >= _MAX_PROPOSALS:
                break
        proposals.sort(key=lambda p: (p.priority != "high", -p.source_authority))
        return proposals
