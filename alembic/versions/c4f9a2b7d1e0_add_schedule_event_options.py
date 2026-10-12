"""Add schedule event type and importance.

Revision ID: c4f9a2b7d1e0
Revises: b84f6a2c1d70
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c4f9a2b7d1e0"
down_revision: str | Sequence[str] | None = "b84f6a2c1d70"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "schedule_event",
        sa.Column(
            "event_type",
            sa.String(length=32),
            nullable=False,
            server_default="general",
        ),
    )
    op.add_column(
        "schedule_event",
        sa.Column(
            "is_important",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("schedule_event", "is_important")
    op.drop_column("schedule_event", "event_type")
