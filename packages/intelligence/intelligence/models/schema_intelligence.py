"""Schema (structured data) section of the SEO Knowledge Object (§4.9).

Observed existing JSON-LD blocks, **inferred** missing/recommended types, and
**proposed** AI-generated JSON-LD that MUST pass ``schema_org_validator`` before
it is stored in ``generated_jsonld``.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

__all__ = [
    "SchemaValidationStatus",
    "SchemaBlock",
    "RecommendedSchema",
    "SchemaIntelligenceSection",
]


class SchemaValidationStatus(str, Enum):
    NOT_VALIDATED = "not_validated"
    VALID = "valid"
    INVALID = "invalid"


class SchemaBlock(BaseModel):
    type: str
    raw_jsonld: str
    element_id: str | None = None


class RecommendedSchema(BaseModel):
    type: str
    reasoning: str | None = None
    priority: int = 0


class SchemaIntelligenceSection(BaseModel):
    existing_schema: list[SchemaBlock] = Field(default_factory=list)  # observed
    missing_schema_types: list[str] = Field(default_factory=list)  # inferred
    recommended_schema: list[RecommendedSchema] = Field(default_factory=list)  # proposed
    generated_jsonld: list[SchemaBlock] = Field(default_factory=list)  # proposed (validated)
    validation_status: SchemaValidationStatus = SchemaValidationStatus.NOT_VALIDATED
    # --- Milestone 2.1 (§13.1/§13.2): the human/AI-chosen primary schema type,
    # distinct from the ranked recommended_schema list. Human-overridable. ---
    selected_schema_type: str | None = None
