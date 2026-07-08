"""Technical SEO Engine output models (§4.1).

Each finding carries a severity, a pass/fail flag, human-readable description,
evidence (the observed value that triggered the check), and an optional
``related_fix_type`` linking to a Milestone 1 FixGenerator where the finding
is directly actionable — following the ``SeoRecommendation.related_fix_type``
pattern threaded through since Milestone 2.1.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

__all__ = [
    "FindingSeverity",
    "TechnicalFinding",
    "TechnicalSeoAudit",
]


class FindingSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class TechnicalFinding(BaseModel):
    """One typed technical SEO finding (§4.1)."""

    check_name: str
    severity: FindingSeverity
    passed: bool
    description: str
    evidence: str | None = None           # observed value that triggered the check
    related_fix_type: str | None = None   # mirrors SeoRecommendation.related_fix_type
    source: str = "observed"              # observed | inferred


class TechnicalSeoAudit(BaseModel):
    """Full technical SEO audit for one page (§4.1)."""

    page_id: str
    site_id: str
    tenant_id: str
    version: int = 1
    findings: list[TechnicalFinding] = Field(default_factory=list)
    sitewide_findings_refs: list[str] = Field(default_factory=list)  # cross-references
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    passed_count: int = 0
    computed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def summary(self) -> dict[str, Any]:
        """Quick counts of findings grouped by severity."""
        return {
            "total": len(self.findings),
            "critical": self.critical_count,
            "high": self.high_count,
            "medium": self.medium_count,
            "passed": self.passed_count,
        }
