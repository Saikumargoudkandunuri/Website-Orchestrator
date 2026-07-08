from engines.shared.db import BacklinkIntelligenceReportRow
from engines.shared.repository_base import EngineRepoMixin
from engines.backlink_intelligence.models import BacklinkIntelligenceReport

__all__ = ["BacklinkIntelligenceReportRepository"]


class BacklinkIntelligenceReportRepository(EngineRepoMixin):
    _row_class = BacklinkIntelligenceReportRow
    _model_class = BacklinkIntelligenceReport
    _scope_col = "site_id"
