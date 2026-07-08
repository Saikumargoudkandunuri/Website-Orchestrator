from engines.shared.db import RecommendationReportRow
from engines.shared.repository_base import EngineRepoMixin
from engines.recommendation.models import RecommendationReport

__all__ = ["RecommendationReportRepository"]


class RecommendationReportRepository(EngineRepoMixin):
    _row_class = RecommendationReportRow
    _model_class = RecommendationReport
    _scope_col = "site_id"
