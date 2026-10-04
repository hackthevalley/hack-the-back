"""Preserve inactive questions and track attendee check-ins.

Revision ID: b84f6a2c1d70
Revises: f19b3d4e5a60
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b84f6a2c1d70"
down_revision: str | Sequence[str] | None = "f19b3d4e5a60"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "forms_question",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "forms_hackathonapplicant",
        sa.Column("checked_in_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("forms_hackathonapplicant", "checked_in_at")
    op.drop_column("forms_question", "is_active")
