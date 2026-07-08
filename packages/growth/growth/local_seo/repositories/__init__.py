"""Local SEO repositories."""
from __future__ import annotations

from growth.db import LocalSeoReportRow
from growth.local_seo.models import LocalSeoReport
from growth.shared.repository_base import GrowthRepoMixin

__all__ = ["LocalSeoRepository"]


class LocalSeoRepository(GrowthRepoMixin):
    """Versioned Local SEO report persistence."""

    _row_class = LocalSeoReportRow
    _model_class = LocalSeoReport
    _scope_col = "site_id"