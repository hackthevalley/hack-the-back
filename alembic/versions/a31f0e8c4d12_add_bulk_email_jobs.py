"""add bulk email jobs

Revision ID: a31f0e8c4d12
Revises: d72b2ec932bf
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a31f0e8c4d12"
down_revision: str | None = "d72b2ec932bf"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "bulk_email_job",
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("total_recipients", sa.Integer(), nullable=False),
        sa.Column("successful", sa.Integer(), nullable=False),
        sa.Column("failed", sa.Integer(), nullable=False),
        sa.Column("error_summary", sa.String(length=2000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("job_id"),
    )
    op.create_index("ix_bulk_email_job_status", "bulk_email_job", ["status"])


def downgrade() -> None:
    op.drop_index("ix_bulk_email_job_status", table_name="bulk_email_job")
    op.drop_table("bulk_email_job")
