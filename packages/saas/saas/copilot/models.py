"""AI Copilot DB models and Pydantic schemas for System 6."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from pydantic import BaseModel, Field
from sqlalchemy import Boolean, DateTime, Float, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

try:
    from sqlalchemy import JSON
except ImportError:
    from sqlalchemy import Text as JSON

from saas.db import SaaSBase

__all__ = [
    "ConversationSessionRow",
    "PromptTemplateRow",
    "AIExplanationRow",
    "ConversationSession",
    "PromptTemplate",
    "AIExplanation",
]


class ConversationSessionRow(SaaSBase):
    """SQLAlchemy Row mapping a Copilot Chat Session."""

    __tablename__ = "saas_copilot_sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    messages_json: Mapped[dict] = mapped_column(JSON, nullable=False)  # stores chat history
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class PromptTemplateRow(SaaSBase):
    """SQLAlchemy Row mapping a reusable prompt layout."""

    __tablename__ = "saas_prompt_templates"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    template_text: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=True)


class AIExplanationRow(SaaSBase):
    """SQLAlchemy Row mapping cached reasoning graph logs."""

    __tablename__ = "saas_ai_explanations"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    goal_id: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    explanation_json: Mapped[dict] = mapped_column(JSON, nullable=False)  # serialised nodes/scores


# ---- Pydantic schemas ----

class ConversationSession(BaseModel):
    id: str
    tenant_id: str
    user_id: str
    messages_json: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PromptTemplate(BaseModel):
    id: str
    tenant_id: str
    name: str
    template_text: str
    description: str | None = None


class AIExplanation(BaseModel):
    id: str
    tenant_id: str
    goal_id: str
    explanation_json: dict[str, Any] = Field(default_factory=dict)
