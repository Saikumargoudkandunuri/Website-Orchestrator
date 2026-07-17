"""Programmatic SEO Engine — generates governed landing-page drafts
(service/city/category/comparison/FAQ pages) from real, already-known site
data (products/services, locations, and competitor comparison targets already
present in the Digital Twin / knowledge object).

Never invents facts: a page is only proposed when the underlying entity (a real
service name, a real city, a real category, a real competitor) is present in
site data. Publishing always goes through the Governance_Layer via the
Publishing_Adapter's ``create_page`` (draft-only) with a real audit + rollback
path (delete the created page).
"""
from __future__ import annotations

from engines.programmatic_seo.models import (
    ProgrammaticPagePlan,
    ProgrammaticSeoReport,
)
from engines.programmatic_seo.service import ProgrammaticSeoService

__all__ = ["ProgrammaticSeoService", "ProgrammaticPagePlan", "ProgrammaticSeoReport"]
