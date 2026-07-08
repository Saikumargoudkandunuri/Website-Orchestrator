"""Content Generation service."""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Any
from intelligence.ai.provider_interface import AIProvider
from intelligence.prompts.base_prompt_template import PromptContext
from growth.shared.content_asset import (
    ContentAsset, ContentAssetType, ContentAssetStatus,
    ContentPayload, ContentSection, MetadataSection, SchemaBlock,
    ASSET_TYPES_REQUIRING_REVIEW,
)
from growth.shared.brand_voice_profile import BrandVoiceProfile
from growth.content_generation.models import ContentGenerationRequest, ContentGenerationReport
from growth.content_generation.repositories import ContentAssetRepository

__all__ = ["ContentGenerationService"]


class ContentGenerationService:
    """Generates ContentAssets using the AI provider and brand voice profile."""

    def __init__(
        self,
        ai_provider: AIProvider,
        repo: ContentAssetRepository,
        tenant_id: str,
    ) -> None:
        self._provider = ai_provider
        self._repo = repo
        self._tenant_id = tenant_id

    def generate(
        self,
        request: ContentGenerationRequest,
        brand_voice: BrandVoiceProfile | None = None,
        review_required_types: frozenset[ContentAssetType] | None = None,
    ) -> ContentAsset:
        """Generate a ContentAsset from the request. Returns saved draft."""
        from intelligence.ai.provider_interface import AICompletionRequest
        from growth.shared.automation.event_bus_interface import DomainEvent
        import json

        bv_context = brand_voice.to_prompt_context() if brand_voice else "No brand voice."
        prompt = (
            f"Generate a {request.asset_type.value} about: {request.topic}.\n"
            f"Target keyword: {request.target_keyword or 'not specified'}.\n"
            f"Language: {request.language}. Style: {request.writing_style}.\n"
            f"Target word count: {request.word_count_target}.\n"
            f"Brand voice: {bv_context}\n"
            f"Missing topics to cover: {', '.join(request.missing_topics_ref) or 'none'}.\n"
            "Return JSON: {title, body_sections: [{section_type, heading, content}], "
            "meta_title, meta_description, cta, generation_reasoning}"
        )
        ai_req = AICompletionRequest(
            prompt=prompt,
            system_prompt="You are an expert SEO content writer. Return valid JSON only.",
            max_tokens=1500,
            temperature=0.3,
            json_mode=True,
            metadata={"capability": "content_generation", "prompt_version": "1.0.0",
                      "asset_type": request.asset_type.value},
        )
        result = self._provider.complete(ai_req)
        if result.is_err:
            raw_text = f"[AI generation failed: {result.error}]"
            sections = [ContentSection(section_type="body", content=raw_text)]
            reasoning = "AI generation failed."
        else:
            raw_text = result.value.raw_text
            try:
                data = json.loads(raw_text)
            except Exception:
                data = {}
            raw_sections = data.get("body_sections", [{"section_type": "body", "content": raw_text}])
            sections = [
                ContentSection(
                    section_type=s.get("section_type", "body"),
                    heading=s.get("heading"),
                    content=s.get("content", ""),
                    word_count=len(s.get("content", "").split()),
                )
                for s in raw_sections
            ]
            reasoning = data.get("generation_reasoning", "")

        total_words = sum(s.word_count for s in sections)
        payload = ContentPayload(
            title=data.get("title", request.topic) if result.is_ok else request.topic,
            body_sections=sections,
            meta=MetadataSection(
                meta_title=data.get("meta_title") if result.is_ok else None,
                meta_description=data.get("meta_description") if result.is_ok else None,
            ),
            cta=data.get("cta") if result.is_ok else None,
            language=request.language,
            writing_style=request.writing_style,
            brand_voice_profile_ref=request.brand_voice_profile_ref,
            word_count=total_words,
            generation_reasoning=reasoning,
        )
        asset_id = uuid.uuid4().hex
        asset = ContentAsset(
            id=asset_id,
            tenant_id=self._tenant_id,
            organization_id=request.organization_id,
            client_id=request.client_id,
            site_id=request.site_id,
            page_id=request.page_id,
            asset_type=request.asset_type,
            status=ContentAssetStatus.DRAFT,
            content_payload=payload,
        )
        return self._repo.save(asset)

    def submit_for_review(self, asset_id: str, actor: str) -> ContentAsset:
        asset = self._repo.get(asset_id)
        if asset is None:
            raise ValueError(f"ContentAsset {asset_id!r} not found.")
        if asset.requires_review():
            new_status = ContentAssetStatus.IN_REVIEW
        else:
            new_status = ContentAssetStatus.PENDING
        updated = asset.transition(new_status, actor, "Submitted for review.")
        return self._repo.save(updated)

    def approve(self, asset_id: str, actor: str, notes: str = "") -> ContentAsset:
        asset = self._repo.get(asset_id)
        if asset is None:
            raise ValueError(f"ContentAsset {asset_id!r} not found.")
        updated = asset.transition(
            ContentAssetStatus.APPROVED, actor, "Approved.", notes=notes or None
        )
        return self._repo.save(updated)

    def reject(self, asset_id: str, actor: str, reason: str) -> ContentAsset:
        asset = self._repo.get(asset_id)
        if asset is None:
            raise ValueError(f"ContentAsset {asset_id!r} not found.")
        updated = asset.transition(ContentAssetStatus.REJECTED, actor, reason)
        updated = updated.model_copy(update={"failure_reason": reason})
        return self._repo.save(updated)

    def publish(self, asset_id: str, actor: str) -> ContentAsset:
        asset = self._repo.get(asset_id)
        if asset is None:
            raise ValueError(f"ContentAsset {asset_id!r} not found.")
        if asset.status != ContentAssetStatus.APPROVED:
            raise ValueError(f"Cannot publish asset in status {asset.status!r}; must be approved.")
        updated = asset.transition(ContentAssetStatus.PUBLISHED, actor, "Published.")
        return self._repo.save(updated)

    def verify(self, asset_id: str, actor: str) -> ContentAsset:
        asset = self._repo.get(asset_id)
        if asset is None:
            raise ValueError(f"ContentAsset {asset_id!r} not found.")
        updated = asset.transition(ContentAssetStatus.VERIFIED, actor, "Verified on live site.")
        return self._repo.save(updated)
