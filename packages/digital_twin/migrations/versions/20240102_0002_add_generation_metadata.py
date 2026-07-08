"""add AI generation metadata to suggested_fixes (Milestone 1)

Adds two nullable columns to ``suggested_fixes`` recording how a fix's
``proposed_value`` was produced when it came from the AI generation layer
(:class:`~core.interfaces.AltTextGenerationService`):

* ``generation_model`` — the model/version that produced the suggestion; and
* ``generation_confidence`` — the model's self-reported confidence (0.0-1.0),
  when available.

Both are nullable, so heuristic/report-only fixes and all existing Milestone 0
rows remain valid and readable after the migration — no data is dropped or
retyped. The change is purely additive and fully reversible (``downgrade`` drops
the two columns). Kept in lockstep with :mod:`digital_twin.models` so the
migration-model sync check (autogenerate) still produces an empty diff.

Revision ID: 0002_generation_metadata
Revises: 0001_initial
Create Date: 2024-01-02 00:00:00

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_generation_metadata"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "suggested_fixes",
        sa.Column("generation_model", sa.String(), nullable=True),
    )
    op.add_column(
        "suggested_fixes",
        sa.Column("generation_confidence", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("suggested_fixes", "generation_confidence")
    op.drop_column("suggested_fixes", "generation_model")
