from engines.shared.db import SeoScoreReportRow
from engines.shared.repository_base import EngineRepoMixin
from engines.seo_scoring.models import SeoScoreReport

__all__ = ["SeoScoreReportRepository"]


class SeoScoreReportRepository(EngineRepoMixin):
    _row_class = SeoScoreReportRow
    _model_class = SeoScoreReport
    _scope_col = "page_id"
