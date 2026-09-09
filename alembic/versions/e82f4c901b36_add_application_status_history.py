"""Add admin application decision history."""
from alembic import op
import sqlalchemy as sa

revision = "e82f4c901b36"
down_revision = "a31f0e8c4d12"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "application_status_history",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("application_id", sa.Uuid(), sa.ForeignKey("forms_application.application_id"), nullable=False),
        sa.Column("admin_id", sa.Uuid(), sa.ForeignKey("account_user.uid"), nullable=False),
        sa.Column("admin_name", sa.String(), nullable=False),
        sa.Column("admin_email", sa.String(), nullable=False),
        sa.Column("previous_status", sa.String(), nullable=False),
        sa.Column("new_status", sa.String(), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_application_status_history_application_id", "application_status_history", ["application_id"])


def downgrade() -> None:
    op.drop_index("ix_application_status_history_application_id", table_name="application_status_history")
    op.drop_table("application_status_history")
