"""add application judging

Revision ID: 7f3c1a2d9e40
Revises: 2c1d5e7a9b30
Create Date: 2026-08-05
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "7f3c1a2d9e40"
down_revision: Union[str, Sequence[str], None] = "2c1d5e7a9b30"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "judging_application_score",
        sa.Column("application_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("mu", sa.Float(), server_default="0", nullable=False),
        sa.Column("sigma_sq", sa.Float(), server_default="1", nullable=False),
        sa.Column("comparison_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["application_id"], ["forms_application.application_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("application_id"),
    )
    op.create_index(
        "ix_judging_application_score_mu", "judging_application_score", ["mu"]
    )

    op.create_table(
        "judging_judge_state",
        sa.Column("judge_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("alpha", sa.Float(), server_default="10", nullable=False),
        sa.Column("beta", sa.Float(), server_default="1", nullable=False),
        sa.Column("left_application_id", postgresql.UUID(as_uuid=True)),
        sa.Column("right_application_id", postgresql.UUID(as_uuid=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["judge_id"], ["account_user.uid"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["left_application_id"],
            ["forms_application.application_id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["right_application_id"],
            ["forms_application.application_id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("judge_id"),
    )
    op.create_index(
        "ix_judging_judge_state_updated_at", "judging_judge_state", ["updated_at"]
    )

    op.create_table(
        "judging_decision",
        sa.Column("decision_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("request_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("judge_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("winner_application_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("loser_application_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["judge_id"], ["account_user.uid"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["winner_application_id"],
            ["forms_application.application_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["loser_application_id"],
            ["forms_application.application_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("decision_id"),
        sa.UniqueConstraint("request_id"),
    )
    op.create_index("ix_judging_decision_judge_id", "judging_decision", ["judge_id"])
    op.create_index(
        "ix_judging_decision_winner_application_id",
        "judging_decision",
        ["winner_application_id"],
    )
    op.create_index(
        "ix_judging_decision_loser_application_id",
        "judging_decision",
        ["loser_application_id"],
    )


def downgrade() -> None:
    op.drop_table("judging_decision")
    op.drop_table("judging_judge_state")
    op.drop_table("judging_application_score")
