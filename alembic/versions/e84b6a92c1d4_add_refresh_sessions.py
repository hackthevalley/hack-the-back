"""add refresh sessions

Revision ID: e84b6a92c1d4
Revises: a31f0e8c4d12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e84b6a92c1d4"
down_revision: str | None = "a31f0e8c4d12"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "account_refresh_session",
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("family_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("token_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("replaced_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["replaced_by_id"],
            ["account_refresh_session.session_id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["account_user.uid"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("session_id"),
    )
    op.create_index(
        op.f("ix_account_refresh_session_family_id"),
        "account_refresh_session",
        ["family_id"],
    )
    op.create_index(
        op.f("ix_account_refresh_session_token_hash"),
        "account_refresh_session",
        ["token_hash"],
        unique=True,
    )
    op.create_index(
        op.f("ix_account_refresh_session_user_id"),
        "account_refresh_session",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_account_refresh_session_user_id"),
        table_name="account_refresh_session",
    )
    op.drop_index(
        op.f("ix_account_refresh_session_token_hash"),
        table_name="account_refresh_session",
    )
    op.drop_index(
        op.f("ix_account_refresh_session_family_id"),
        table_name="account_refresh_session",
    )
    op.drop_table("account_refresh_session")
