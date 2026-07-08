"""Reporting Engine models (§4.6)."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

__all__ = [
    "ReportType",
    "ReportFormat",
    "ReportDefinition",
    "ReportArtifact",
    "BrandingConfig",
]


class ReportType:
    """Report types that can be generated (§4.6)."""
    EXECUTIVE = "executive"
    SEO = "seo"
    TECHNICAL = "technical"
    CONTENT = "content"
    GROWTH = "growth"
    KEYWORD = "keyword"
    BACKLINK = "backlink"
    LOCAL_SEO = "local_seo"
    REPUTATION = "reputation"


class ReportFormat:
    """Output formats for reports (§4.6)."""
    PDF = "pdf"
    CSV = "csv"
    EXCEL = "excel"
    JSON = "json"


@dataclass(frozen=True)
class BrandingConfig:
    """White-label branding configuration from Agency Management (§4.6, §4.7)."""
    logo_url: str | None = None
    primary_color: str | None = None
    secondary_color: str | None = None
    client_facing_name: str | None = None
    footer_text: str | None = None


@dataclass(frozen=True)
class ReportDefinition:
    """
    Report generation configuration (§4.6).
    
    Scheduled reports use this definition + cron expression.
    """
    id: str
    report_type: str  # ReportType constant
    format: str  # ReportFormat constant
    schedule: str | None  # CronExpression string, or None for one-time
    branding_ref: str  # Organization ID for branding lookup
    source_engine_refs: list[str]  # Engine names whose outputs to include
    filters: dict[str, Any] = field(default_factory=dict)  # Date range, pages, etc.


@dataclass(frozen=True)
class ReportArtifact:
    """
    Generated report output (§4.6).
    
    CRITICAL: This engine does NOT compute new metrics - only synthesizes
    existing engine outputs into presentation format.
    """
    id: str
    report_definition_ref: str
    format: str
    storage_ref: str  # File path or blob storage key
    generated_at: datetime
    data_completeness_summary: dict[str, Any]  # Rolls up data_source/data_completeness from all source engines
    file_size_bytes: int | None = None
    generation_duration_ms: int | None = None
