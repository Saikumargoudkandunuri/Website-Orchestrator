"""Abstract provider interface for AI adapters."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import AsyncIterator, List
from decimal import Decimal

from .schemas import ChatRequest, ChatResponse, GenerateRequest, GenerateResponse, EmbedRequest, EmbedResponse, ModelInfo, TokenUsage


class BaseProvider(ABC):
	"""Abstract provider interface. Adapters must implement these methods."""

	name: str

	@abstractmethod
	async def initialize(self) -> None:
		...

	@abstractmethod
	async def health(self) -> str:
		...

	@abstractmethod
	async def chat(self, request: ChatRequest) -> ChatResponse:
		...

	@abstractmethod
	async def generate(self, request: GenerateRequest) -> GenerateResponse:
		...

	@abstractmethod
	async def embedding(self, request: EmbedRequest) -> EmbedResponse:
		...

	@abstractmethod
	async def stream(self, request: ChatRequest) -> AsyncIterator[str]:
		...

	@abstractmethod
	async def models(self) -> List[ModelInfo]:
		...

	@abstractmethod
	async def estimate_cost(self, tokens: TokenUsage) -> Decimal:
		...

	@abstractmethod
	async def shutdown(self) -> None:
		...
