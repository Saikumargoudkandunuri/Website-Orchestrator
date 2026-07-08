"""Content Optimization repositories."""
from __future__ import annotations

from growth.content_optimization.models import ContentOptimizationReport
from growth.db import ContentOptimizationReportRow
from growth.shared.repository_base import GrowthRepoMixin

__all__ = ["ContentOptimizationRepository"]


class ContentOptimizationRepository(GrowthRepoMixin):
    """Versioned Content Optimization report persistence."""

    _row_class = ContentOptimizationReportRow
    _model_class = ContentOptimizationReport
    _scope_col = "page_id"