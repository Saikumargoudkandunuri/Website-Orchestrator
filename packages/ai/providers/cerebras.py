"""Cerebras provider stub."""
from __future__ import annotations

from decimal import Decimal
from typing import AsyncIterator

from ai.provider import BaseProvider
from ai.schemas import ChatRequest, ChatResponse, GenerateRequest, GenerateResponse, EmbedRequest, EmbedResponse, ModelInfo, TokenUsage


class Provider(BaseProvider):
	name = "cerebras"

	async def initialize(self) -> None:
		return None

	async def health(self) -> str:
		return "healthy"

	async def chat(self, request: ChatRequest) -> ChatResponse:
		return ChatResponse(text="[cerebras stub] chat not implemented", tokens=TokenUsage())

	async def generate(self, request: GenerateRequest) -> GenerateResponse:
		return GenerateResponse(text="[cerebras stub] generate not implemented", tokens=TokenUsage())

	async def embedding(self, request: EmbedRequest) -> EmbedResponse:
		return EmbedResponse(embeddings=[[0.0]], tokens=TokenUsage())

	async def stream(self, request: ChatRequest) -> AsyncIterator[str]:
		yield ""

	async def models(self) -> list[ModelInfo]:
		return [ModelInfo(provider="cerebras", model="cerebras-model")]

	async def estimate_cost(self, tokens: TokenUsage) -> Decimal:
		return Decimal("0.0")

	async def shutdown(self) -> None:
		return None
