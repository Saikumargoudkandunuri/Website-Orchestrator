from engines.shared.db import TopicalAuthorityReportRow
from engines.shared.repository_base import EngineRepoMixin
from engines.topical_authority.models import TopicalAuthorityReport

__all__ = ["TopicalAuthorityReportRepository"]


class TopicalAuthorityReportRepository(EngineRepoMixin):
    _row_class = TopicalAuthorityReportRow
    _model_class = TopicalAuthorityReport
    _scope_col = "site_id"
