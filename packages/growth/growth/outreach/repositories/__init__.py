"""Outreach repositories."""
from __future__ import annotations

from growth.db import OutreachReportRow
from growth.outreach.models import OutreachReport
from growth.shared.repository_base import GrowthRepoMixin

__all__ = ["OutreachRepository"]


class OutreachRepository(GrowthRepoMixin):
    """Versioned Outreach report persistence."""

    _row_class = OutreachReportRow
    _model_class = OutreachReport
    _scope_col = "site_id"