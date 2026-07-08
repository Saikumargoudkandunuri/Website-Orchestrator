"""Local SEO Engine models (§4.3)."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

__all__ = [
    "LocalSeoProfile",
    "NapConsistencyResult",
    "NapInconsistency",
    "LocalSeoReport",
]


@dataclass(frozen=True)
class LocalSeoProfile:
    """
    Local SEO profile per physical location (§4.3).
    
    Cross-referenced to location landing page via M2 IdentitySection.
    """
    location_id: str
    page_id: str | None  # Landing page for this location
    name: str
    address: str
    phone: str
    
    # GBP optimization (provider-fake)
    gbp_categories: list[str] = field(default_factory=list)
    gbp_attributes: list[str] = field(default_factory=list)
    gbp_hours_complete: bool = False
    gbp_photo_count: int = 0
    gbp_post_cadence_score: float = 0.0
    
    # Citation management (provider-fake)
    citation_count: int = 0
    citation_consistency_score: float = 1.0
    
    # Local ranking (delegates to Rank Tracking Engine)
    local_ranking_summary: dict[str, Any] = field(default_factory=dict)
    
    # Location schema validation (reuses M2 schema_org_validator)
    has_local_business_schema: bool = False
    schema_validation_errors: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class NapInconsistency:
    """NAP (Name/Address/Phone) inconsistency between pages (§4.3)."""
    page_id_1: str
    page_id_2: str
    field: str  # "name" | "address" | "phone"
    value_1: str
    value_2: str
    severity: str  # "critical" | "warning"


@dataclass(frozen=True)
class NapConsistencyResult:
    """
    NAP consistency checking result (§4.3).
    
    REAL capability (not provider-fake): cross-references every page's structured
    contact data via M2 EeatSection.contact_info_present and LocalBusiness schema
    blocks from M2 SchemaIntelligenceSection.
    """
    is_consistent: bool
    inconsistencies: list[NapInconsistency]
    pages_checked: list[str]
    confidence_score: float  # 0.0-1.0, based on data completeness


@dataclass(frozen=True)
class LocalSeoReport:
    """
    Local SEO Report (§4.3).
    
    Sitewide/per-location scope. Contains real NAP consistency + provider-fake GBP/citations.
    """
    site_id: str
    locations: list[LocalSeoProfile]
    nap_consistency: NapConsistencyResult
    local_seo_score: dict[str, Any]  # SeoScoreBreakdown-shaped, transparent breakdown
    computed_at: datetime
    version: int
    data_source: str = "deterministic+provider_fake"  # NAP is deterministic, GBP/citations are fake
    data_completeness: float = 0.6  # Honest about provider-fake portions
