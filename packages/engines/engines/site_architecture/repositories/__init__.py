from engines.shared.db import SiteArchitectureReportRow
from engines.shared.repository_base import EngineRepoMixin
from engines.site_architecture.models import SiteArchitectureReport

__all__ = ["SiteArchitectureReportRepository"]


class SiteArchitectureReportRepository(EngineRepoMixin):
    _row_class = SiteArchitectureReportRow
    _model_class = SiteArchitectureReport
    _scope_col = "site_id"
