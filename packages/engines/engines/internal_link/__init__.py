"""Internal Link Engine — real internal-link analysis from crawl data.

Operates on the actual crawled pages in the Digital Twin (never synthesized
fixtures): it resolves each page's outbound links to internal targets by URL
match, computes authority flow (PageRank, reused from the Site Architecture
engine), detects orphan and weak-authority pages, and proposes concrete,
evidence-backed internal links from high-authority related pages to the pages
that need equity.

Honest scope boundary: the crawler does not currently capture link anchor text
or resolve pages to WordPress page ids, so proposals are governed
recommendations (a human/approval step), not silent auto-publish. Suggested
anchors are derived from the real target page title/slug — never fabricated
metrics.
"""
from __future__ import annotations

from engines.internal_link.models import (
    InternalLinkProposal,
    InternalLinkReport,
    PageAuthority,
)
from engines.internal_link.service import InternalLinkService

__all__ = [
    "InternalLinkService",
    "InternalLinkReport",
    "InternalLinkProposal",
    "PageAuthority",
]
