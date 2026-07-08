from engines.shared.db import KeywordEngineReportRow
from engines.shared.repository_base import EngineRepoMixin
from engines.keyword_intelligence.models import KeywordEngineReport

__all__ = ["KeywordEngineReportRepository"]


class KeywordEngineReportRepository(EngineRepoMixin):
    _row_class = KeywordEngineReportRow
    _model_class = KeywordEngineReport
    _scope_col = "page_id"
