"""Shared BrandVoiceProfile model — one model, three consumers (§1.1, §4.1).

The BrandVoiceProfile is consumed identically by:
1. Content Generation Engine (§4.1) — injected into every generation prompt.
2. Reputation Management Engine (§4.4) — injected into review response drafts.
3. Outreach Engine (§4.9) — injected into email template drafts.

One model, three consumers — no duplicated brand-voice configuration.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

__all__ = ["BrandVoiceProfile"]


class BrandVoiceProfile(BaseModel):
    """Defines the brand voice and writing style for a site/client.

    Injected into every generation-adjacent prompt's context via the shared
    model — a single definition consumed identically by Content Generation,
    Reputation responses, and Outreach templates.
    """

    site_id: str
    organization_id: str | None = None
    client_id: str | None = None

    # --- Tone descriptors ---
    tone_descriptors: list[str] = Field(
        default_factory=list,
        description="e.g. ['professional', 'approachable', 'authoritative']",
    )
    writing_style: str = "professional"  # e.g. professional | conversational | academic | casual

    # --- Vocabulary preferences ---
    preferred_vocabulary: list[str] = Field(
        default_factory=list,
        description="Words/phrases to prefer in generated content.",
    )
    forbidden_phrases: list[str] = Field(
        default_factory=list,
        description="Words/phrases to never use in generated content.",
    )

    # --- Example passages (for few-shot injection) ---
    example_passages: list[str] = Field(
        default_factory=list,
        description="Short example passages in the brand voice, for prompt injection.",
    )

    # --- Target audience ---
    target_audience: str | None = None

    # --- CTA style ---
    cta_style: str | None = None  # e.g. "action-oriented", "soft suggestion"

    def to_prompt_context(self) -> str:
        """Render this profile as a concise prompt context string."""
        parts = []
        if self.tone_descriptors:
            parts.append(f"Tone: {', '.join(self.tone_descriptors)}.")
        if self.writing_style:
            parts.append(f"Style: {self.writing_style}.")
        if self.target_audience:
            parts.append(f"Target audience: {self.target_audience}.")
        if self.preferred_vocabulary:
            parts.append(f"Prefer: {', '.join(self.preferred_vocabulary[:5])}.")
        if self.forbidden_phrases:
            parts.append(f"Never use: {', '.join(self.forbidden_phrases[:5])}.")
        if self.example_passages:
            parts.append("Example passage: " + self.example_passages[0][:200])
        return " ".join(parts) or "No brand voice profile provided."
