"""Schema Engine — detects missing/incomplete schema.org markup from real
crawl data and proposes concrete JSON-LD blocks.

Operates on ``CrawledPage.schema_types`` (captured by the crawler from actual
``<script type="application/ld+json">`` blocks) and page signals
(url/title/headings) already persisted in the Digital Twin. Never fabricates
page facts: every generated schema payload is built only from fields observed
on the page.
"""
from __future__ import annotations

from engines.schema_engine.models import SchemaGap, SchemaProposal, SchemaReport
from engines.schema_engine.service import SchemaEngineService

__all__ = ["SchemaEngineService", "SchemaGap", "SchemaProposal", "SchemaReport"]
