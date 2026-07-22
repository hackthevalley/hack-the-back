"""add account security state

Revision ID: 2c1d5e7a9b30
Revises: bf8b33c13520
Create Date: 2026-07-22

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "2c1d5e7a9b30"
down_revision: Union[str, Sequence[str], None] = "bf8b33c13520"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "account_user",
        sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "account_user",
        sa.Column(
            "failed_login_attempts", sa.Integer(), nullable=False, server_default="0"
        ),
    )
    op.add_column(
        "account_user", sa.Column("locked_until", sa.DateTime(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("account_user", "locked_until")
    op.drop_column("account_user", "failed_login_attempts")
    op.drop_column("account_user", "token_version")
