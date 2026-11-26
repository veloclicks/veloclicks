"""Track completed Strava synchronisation intervals.

Revision ID: c4a8d1e7b920
Revises: ae813e5c0a1f
"""
from alembic import op
import sqlalchemy as sa

revision = "c4a8d1e7b920"
down_revision = "ae813e5c0a1f"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "sync_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("vc_user.id"), nullable=False),
        sa.Column("from_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("to_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("from_date < to_date", name="ck_sync_history_interval"),
    )
    op.create_index("ix_sync_history_user_dates", "sync_history",
                    ["user_id", "from_date", "to_date"])


def downgrade():
    op.drop_index("ix_sync_history_user_dates", table_name="sync_history")
    op.drop_table("sync_history")
