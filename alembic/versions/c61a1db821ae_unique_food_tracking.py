"""enforce unique food tracking per user and meal

Revision ID: c61a1db821ae
Revises: 7f3c1a2d9e40
Create Date: 2026-08-06
"""

from typing import Sequence, Union

from alembic import op

revision: str = "c61a1db821ae"
down_revision: Union[str, Sequence[str], None] = "7f3c1a2d9e40"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        DELETE FROM food_tracking
        WHERE id IN (
            SELECT id
            FROM (
                SELECT id, ROW_NUMBER() OVER (
                    PARTITION BY user_id, meal_id
                    ORDER BY checkin_time, id
                ) AS duplicate_number
                FROM food_tracking
            ) duplicates
            WHERE duplicate_number > 1
        )
        """
    )
    op.create_unique_constraint(
        "uq_food_tracking_user_meal",
        "food_tracking",
        ["user_id", "meal_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_food_tracking_user_meal", "food_tracking", type_="unique"
    )
