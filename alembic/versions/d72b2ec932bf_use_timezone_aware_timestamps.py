"""use timezone-aware timestamps

Revision ID: d72b2ec932bf
Revises: c61a1db821ae
Create Date: 2026-08-06
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d72b2ec932bf"
down_revision: Union[str, Sequence[str], None] = "c61a1db821ae"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _make_timezone_aware(table: str, column: str) -> None:
    op.alter_column(
        table,
        column,
        existing_type=sa.DateTime(),
        type_=sa.DateTime(timezone=True),
        postgresql_using=f"{column} AT TIME ZONE 'UTC'",
    )


def _make_timezone_naive(table: str, column: str) -> None:
    op.alter_column(
        table,
        column,
        existing_type=sa.DateTime(timezone=True),
        type_=sa.DateTime(),
        postgresql_using=f"{column} AT TIME ZONE 'UTC'",
    )


def upgrade() -> None:
    for column in (
        "locked_until",
        "last_password_reset_request",
        "last_activation_email_sent",
    ):
        _make_timezone_aware("account_user", column)
    for column in ("created_at", "updated_at"):
        _make_timezone_aware("forms_application", column)
    _make_timezone_aware("food_tracking", "checkin_time")


def downgrade() -> None:
    _make_timezone_naive("food_tracking", "checkin_time")
    for column in ("created_at", "updated_at"):
        _make_timezone_naive("forms_application", column)
    for column in (
        "locked_until",
        "last_password_reset_request",
        "last_activation_email_sent",
    ):
        _make_timezone_naive("account_user", column)
