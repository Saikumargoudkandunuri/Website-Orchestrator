"""Reputation Management repositories."""
from __future__ import annotations

from growth.db import ReputationReportRow
from growth.reputation_management.models import ReputationReport
from growth.shared.repository_base import GrowthRepoMixin

__all__ = ["ReputationRepository"]


class ReputationRepository(GrowthRepoMixin):
    """Versioned Reputation report persistence."""

    _row_class = ReputationReportRow
    _model_class = ReputationReport
    _scope_col = "site_id"