from engines.shared.db import ContentEngineReportRow
from engines.shared.repository_base import EngineRepoMixin
from engines.content_intelligence.models import ContentEngineReport

__all__ = ["ContentEngineReportRepository"]


class ContentEngineReportRepository(EngineRepoMixin):
    _row_class = ContentEngineReportRow
    _model_class = ContentEngineReport
    _scope_col = "page_id"
