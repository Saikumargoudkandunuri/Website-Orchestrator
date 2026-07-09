"""Pydantic schemas for AI requests and responses."""
from __future__ import annotations

from pydantic import BaseModel, Field
from typing import List, Optional
from decimal import Decimal


class TokenUsage(BaseModel):
	input_tokens: int = 0
	output_tokens: int = 0


class ModelInfo(BaseModel):
	provider: str
	model: str
	description: Optional[str] = None


class ChatRequest(BaseModel):
	messages: List[dict]
	model: str
	max_tokens: Optional[int] = None


class ChatResponse(BaseModel):
	text: str
	tokens: TokenUsage = Field(default_factory=TokenUsage)


class GenerateRequest(BaseModel):
	prompt: str
	model: str
	max_tokens: Optional[int] = None


class GenerateResponse(BaseModel):
	text: str
	tokens: TokenUsage = Field(default_factory=TokenUsage)


class EmbedRequest(BaseModel):
	input: List[str]
	model: str


class EmbedResponse(BaseModel):
	embeddings: List[List[float]]
	tokens: TokenUsage = Field(default_factory=TokenUsage)
