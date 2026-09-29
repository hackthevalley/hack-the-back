"""add schedule events

Revision ID: f19b3d4e5a60
Revises: e82f4c901b36
Create Date: 2026-09-29
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f19b3d4e5a60"
down_revision: Union[str, Sequence[str], None] = "e82f4c901b36"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "schedule_event",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("description", sa.String(length=1000), nullable=True),
        sa.Column("location", sa.String(length=160), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_schedule_event_starts_at"), "schedule_event", ["starts_at"]
    )
    op.create_index(op.f("ix_schedule_event_ends_at"), "schedule_event", ["ends_at"])


def downgrade() -> None:
    op.drop_index(op.f("ix_schedule_event_ends_at"), table_name="schedule_event")
    op.drop_index(op.f("ix_schedule_event_starts_at"), table_name="schedule_event")
    op.drop_table("schedule_event")
