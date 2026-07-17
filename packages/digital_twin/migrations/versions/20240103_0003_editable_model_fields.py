"""add editable-model fields to pages and links (Milestone 4)

Turns the Digital_Twin into the authoritative editable model of the site. The
change is purely additive — new nullable columns on the existing ``pages`` and
``links`` tables, no new tables — so every existing row and all prior migrations
remain valid, and the six-table shape is unchanged.

``pages`` gains ``slug``, ``canonical_url``, ``headings`` (JSON text),
``schema_types`` (JSON text), ``wp_page_id`` and ``wp_post_type`` (the stable
URL -> WordPress page/post mapping). ``links`` gains ``anchor_text``, ``rel``,
``is_internal`` and ``to_page_id`` (the resolved internal link graph). All
columns are nullable so the migration applies safely to populated databases and
``downgrade`` cleanly drops them.

Kept in lockstep with :mod:`digital_twin.models` so the migration-model sync
check (autogenerate) still produces an empty diff.

Revision ID: 0003_editable_model_fields
Revises: 0002_generation_metadata
Create Date: 2024-01-03 00:00:00

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003_editable_model_fields"
down_revision: str | None = "0002_generation_metadata"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("pages", sa.Column("slug", sa.String(), nullable=True))
    op.add_column("pages", sa.Column("canonical_url", sa.String(), nullable=True))
    op.add_column("pages", sa.Column("headings", sa.Text(), nullable=True))
    op.add_column("pages", sa.Column("schema_types", sa.Text(), nullable=True))
    op.add_column("pages", sa.Column("wp_page_id", sa.Integer(), nullable=True))
    op.add_column("pages", sa.Column("wp_post_type", sa.String(), nullable=True))

    op.add_column("links", sa.Column("anchor_text", sa.String(), nullable=True))
    op.add_column("links", sa.Column("rel", sa.String(), nullable=True))
    op.add_column("links", sa.Column("is_internal", sa.Boolean(), nullable=True))
    op.add_column("links", sa.Column("to_page_id", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("links", "to_page_id")
    op.drop_column("links", "is_internal")
    op.drop_column("links", "rel")
    op.drop_column("links", "anchor_text")

    op.drop_column("pages", "wp_post_type")
    op.drop_column("pages", "wp_page_id")
    op.drop_column("pages", "schema_types")
    op.drop_column("pages", "headings")
    op.drop_column("pages", "canonical_url")
    op.drop_column("pages", "slug")
