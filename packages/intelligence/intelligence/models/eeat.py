"""EEAT (Experience, Expertise, Authoritativeness, Trust) section (§4.11).

Observed presence signals (author, contact/organization info, citations) plus
**inferred** trust and external-authority signals. External authority is
nullable/future — it depends on data sources not present this milestone.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

__all__ = ["AuthorInfo", "Citation", "EeatSection"]


class AuthorInfo(BaseModel):
    name: str | None = None
    url: str | None = None
    bio_present: bool = False


class Citation(BaseModel):
    url: str
    anchor_text: str | None = None
    authoritative: bool | None = None


class EeatSection(BaseModel):
    author: AuthorInfo | None = None  # observed if present
    trust_signals: list[str] = Field(default_factory=list)  # inferred
    contact_info_present: bool = False  # observed
    organization_info_present: bool = False  # observed
    citations: list[Citation] = Field(default_factory=list)  # observed
    external_authority_signals: list[str] = Field(default_factory=list)  # inferred/future
