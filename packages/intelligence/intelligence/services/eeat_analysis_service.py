"""EEAT analysis (§4.11). Mostly deterministic observation of trust signals."""

from __future__ import annotations

import re

from intelligence.models.eeat import Citation, EeatSection
from intelligence.services.base import AnalysisContext, AnalyzerService

__all__ = ["EeatAnalysisService"]

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE_RE = re.compile(r"\+?\d[\d\s().-]{7,}\d")
_ADDRESS_HINT_RE = re.compile(
    r"\b(street|st\.|road|rd\.|avenue|ave\.|suite|floor|pincode|zip|address)\b",
    re.IGNORECASE,
)


class EeatAnalysisService(AnalyzerService):
    section = "eeat"

    def analyze(self, ctx: AnalysisContext) -> None:
        text = ctx.extracted.text
        url = ctx.page.url

        has_phone = bool(_PHONE_RE.search(text))
        has_email = bool(_EMAIL_RE.search(text))
        has_address = bool(_ADDRESS_HINT_RE.search(text))
        is_https = url.lower().startswith("https://")

        trust_signals: list[str] = []
        if is_https:
            trust_signals.append("served over HTTPS")
        if has_phone:
            trust_signals.append("has a phone number")
        if has_email:
            trust_signals.append("has an email address")
        if has_address:
            trust_signals.append("has a physical address")

        citations = [
            Citation(url=link.url)
            for link in ctx.page.links
            if link.url.startswith("http") and not link.url.startswith(url)
        ]

        ctx.ko.eeat = EeatSection(
            trust_signals=trust_signals,
            contact_info_present=has_phone or has_email,
            organization_info_present=has_address or has_phone,
            citations=citations[:20],
        )
