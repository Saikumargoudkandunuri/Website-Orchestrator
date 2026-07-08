"""Collaboration DB models and Pydantic schemas for System 5."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import Boolean, DateTime, Float, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

try:
    from sqlalchemy import JSON
except ImportError:
    from sqlalchemy import Text as JSON

from saas.db import SaaSBase

__all__ = [
    "ThreadRow",
    "CommentRow",
    "MentionRow",
    "NotificationRow",
    "DecisionLogRow",
    "PresenceRecordRow",
    "Thread",
    "Comment",
    "Mention",
    "Notification",
    "DecisionLog",
    "PresenceRecord",
]


class ThreadRow(SaaSBase):
    """SQLAlchemy Row mapping a discussion Thread."""

    __tablename__ = "saas_collab_threads"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    target_node_id: Mapped[str] = mapped_column(String, nullable=False, index=True)  # maps to canvas node / step ID
    title: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CommentRow(SaaSBase):
    """SQLAlchemy Row mapping comments inside discussion threads."""

    __tablename__ = "saas_collab_comments"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    thread_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    author: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)  # sanitized html content
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class MentionRow(SaaSBase):
    """SQLAlchemy Row mapping user mentions."""

    __tablename__ = "saas_collab_mentions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    comment_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    mentioned_user_id: Mapped[str] = mapped_column(String, nullable=False, index=True)


class NotificationRow(SaaSBase):
    """SQLAlchemy Row mapping inside-app notifications."""

    __tablename__ = "saas_collab_notifications"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    message: Mapped[str] = mapped_column(String, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class DecisionLogRow(SaaSBase):
    """SQLAlchemy Row mapping immutable signed decisions history."""

    __tablename__ = "saas_collab_decision_logs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    goal_id: Mapped[str] = mapped_column(String, nullable=False)
    actor: Mapped[str] = mapped_column(String, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    votes_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    signature: Mapped[str] = mapped_column(String, nullable=False)  # cryptographically signed
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class PresenceRecordRow(SaaSBase):
    """SQLAlchemy Row mapping temporary active user presence status."""

    __tablename__ = "saas_collab_presence"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)  # "online", "away"
    last_active_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


# ---- Pydantic schemas ----

class Thread(BaseModel):
    id: str
    tenant_id: str
    target_node_id: str
    title: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Comment(BaseModel):
    id: str
    tenant_id: str
    thread_id: str
    author: str
    content: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("content")
    def clean_html(cls, v: str) -> str:
        """Sanitize comments input, stripping dangerous HTML tags."""
        # Simple bleach-like regex/strip sanitizer to avoid external network fetch
        import re
        clean = re.sub(r"<script.*?>.*?</script>", "", v, flags=re.DOTALL)
        clean = re.sub(r"on\w+\s*=\s*\".*?\"", "", clean)  # onload, onerror attributes
        clean = re.sub(r"on\w+\s*=\s*'.*?'", "", clean)
        return clean


class Mention(BaseModel):
    id: str
    tenant_id: str
    comment_id: str
    mentioned_user_id: str


class Notification(BaseModel):
    id: str
    tenant_id: str
    user_id: str
    message: str
    is_read: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DecisionLog(BaseModel):
    id: str
    tenant_id: str
    goal_id: str
    actor: str
    rationale: str
    votes_json: dict[str, Any] = Field(default_factory=dict)
    signature: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PresenceRecord(BaseModel):
    id: str
    tenant_id: str
    user_id: str
    status: str
    last_active_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
