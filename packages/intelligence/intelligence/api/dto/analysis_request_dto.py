"""Request DTOs for the intelligence API (§10, §13.6)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

__all__ = ["AnalyzeRequest", "PatchFieldsRequest"]


class AnalyzeRequest(BaseModel):
    """Body for ``POST /intelligence/pages/{page_id}/analyze``."""

    capabilities: list[str] | None = Field(
        default=None,
        description="Optional subset of section/capability names to run; omit for the full suite.",
    )
    force_regenerate_overrides: bool = Field(
        default=False,
        description="When true, human overrides are regenerated instead of carried forward (§13.3).",
    )


class PatchFieldsRequest(BaseModel):
    """Body for ``PATCH /intelligence/pages/{page_id}/fields`` (§13.6).

    ``fields`` maps a dotted field path (e.g.
    ``"metadata.meta_description.proposed_value"`` or
    ``"keyword_intelligence.primary_focus_keyphrase"``) to the human-supplied
    value. Each accepted edit sets ``override_source = "human"`` and is recorded
    in the KnowledgeObject's override registry; a path listed in
    ``immutable_fields`` is rejected.
    """

    fields: dict[str, Any] = Field(..., description="Dotted field path -> new value.")
    actor: str = Field(..., min_length=1, description="Who is making the edit.")
