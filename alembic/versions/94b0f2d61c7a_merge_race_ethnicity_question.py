"""merge renamed race ethnicity question

Revision ID: 94b0f2d61c7a
Revises: 2c1d5e7a9b30
Create Date: 2026-08-05
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "94b0f2d61c7a"
down_revision: Union[str, Sequence[str], None] = "2c1d5e7a9b30"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

OLD_LABEL = "Race/Ethnicity"
NEW_LABEL = "Race/Ethnicity (Select all that apply)"


def upgrade() -> None:
    connection = op.get_bind()
    old_id = connection.execute(
        sa.text("SELECT question_id FROM forms_question WHERE label = :label"),
        {"label": OLD_LABEL},
    ).scalar_one_or_none()
    new_id = connection.execute(
        sa.text("SELECT question_id FROM forms_question WHERE label = :label"),
        {"label": NEW_LABEL},
    ).scalar_one_or_none()

    if old_id is None:
        return
    if new_id is None:
        connection.execute(
            sa.text(
                "UPDATE forms_question SET label = :new_label "
                "WHERE question_id = :old_id"
            ),
            {"new_label": NEW_LABEL, "old_id": old_id},
        )
        return

    connection.execute(
        sa.text(
            """
            UPDATE forms_answer AS canonical
            SET answer = legacy.answer
            FROM forms_answer AS legacy
            WHERE canonical.question_id = :new_id
              AND legacy.question_id = :old_id
              AND canonical.application_id = legacy.application_id
              AND NULLIF(BTRIM(canonical.answer), '') IS NULL
              AND NULLIF(BTRIM(legacy.answer), '') IS NOT NULL
            """
        ),
        {"new_id": new_id, "old_id": old_id},
    )
    connection.execute(
        sa.text("DELETE FROM forms_answer WHERE question_id = :old_id"),
        {"old_id": old_id},
    )
    connection.execute(
        sa.text("DELETE FROM forms_question WHERE question_id = :old_id"),
        {"old_id": old_id},
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE forms_question SET label = :old_label WHERE label = :new_label"
        ).bindparams(old_label=OLD_LABEL, new_label=NEW_LABEL)
    )
