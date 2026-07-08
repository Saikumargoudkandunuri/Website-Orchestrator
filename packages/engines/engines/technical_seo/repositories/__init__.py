from engines.shared.db import TechnicalSeoAuditRow
from engines.shared.repository_base import EngineRepoMixin
from engines.technical_seo.models import TechnicalSeoAudit

__all__ = ["TechnicalSeoAuditRepository"]


class TechnicalSeoAuditRepository(EngineRepoMixin):
    _row_class = TechnicalSeoAuditRow
    _model_class = TechnicalSeoAudit
    _scope_col = "page_id"
