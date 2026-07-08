from engines.shared.db import OpportunityReportRow
from engines.shared.repository_base import EngineRepoMixin
from engines.opportunity.models import OpportunityReport

__all__ = ["OpportunityReportRepository"]


class OpportunityReportRepository(EngineRepoMixin):
    _row_class = OpportunityReportRow
    _model_class = OpportunityReport
    _scope_col = "site_id"
