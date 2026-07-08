"""Premium UX DB models and schemas for System 8."""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field
from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from saas.db import SaaSBase

__all__ = [
    "UserUiPreferencesRow",
    "UserUiPreferences",
]


class UserUiPreferencesRow(SaaSBase):
    """SQLAlchemy Row mapping a user's display preferences (dark/light, dynamic themes)."""

    __tablename__ = "saas_user_ui_preferences"

    user_id: Mapped[str] = mapped_column(String, primary_key=True)
    theme_mode: Mapped[str] = mapped_column(String, nullable=False, default="dark")  # "dark", "light", "system"
    enable_audio: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    display_density: Mapped[str] = mapped_column(String, nullable=False, default="cozy")  # "compact", "cozy", "spacious"


# ---- Pydantic schemas ----

class UserUiPreferences(BaseModel):
    user_id: str
    theme_mode: str = "dark"
    enable_audio: bool = True
    display_density: str = "cozy"
