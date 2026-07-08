from engines.shared.db import CompetitorIntelligenceReportRow
from engines.shared.repository_base import EngineRepoMixin
from engines.competitor_intelligence.models import CompetitorIntelligenceReport

__all__ = ["CompetitorIntelligenceReportRepository"]


class CompetitorIntelligenceReportRepository(EngineRepoMixin):
    _row_class = CompetitorIntelligenceReportRow
    _model_class = CompetitorIntelligenceReport
    _scope_col = "site_id"
