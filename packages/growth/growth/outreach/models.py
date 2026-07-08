"""Outreach & Link Building Engine models (§4.9)."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

__all__ = ["Prospect", "Campaign", "OutreachReport"]


@dataclass(frozen=True)
class Prospect:
    """Prospect entity for link building (§4.9)."""
    prospect_id: str
    domain: str
    contact_email: str | None
    contact_name: str | None
    qualification_score: float  # Heuristic + provider-data-dependent
    status: str  # "new", "contacted", "responded", "accepted", "rejected"
    notes: str = ""


@dataclass(frozen=True)
class Campaign:
    """Outreach campaign (§4.9). Campaign execution (email sending) out of scope."""
    campaign_id: str
    name: str
    prospects: list[str]  # Prospect IDs
    template_ref: str  # Email template (uses BrandVoiceProfile)
    status: str  # "draft", "active", "paused", "completed"
    sent_count: int = 0
    response_count: int = 0


@dataclass(frozen=True)
class OutreachReport:
    """Outreach & Link Building Report (§4.9). Architecture only per spec."""
    site_id: str
    prospects: list[Prospect]
    campaigns: list[Campaign]
    opportunity_scores: dict[str, float]  # Cross-references M3 Backlink Intelligence
    computed_at: datetime
    version: int
    data_source: str = "provider_fake"
    data_completeness: float = 0.3  # Honest about architecture-only status
