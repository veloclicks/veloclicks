"""Index stored activities for date-ordered pages by owner.

Revision ID: ae813e5c0a1f
Revises: b3a7c9d2e541
"""

from alembic import op

revision = "ae813e5c0a1f"
down_revision = "b3a7c9d2e541"
branch_labels = None
depends_on = None

INDEX = "ix_vc_strava_activity_user_date_id"
TABLE = "vc_strava_activity"


def upgrade():
    """Build the index without blocking writes to PostgreSQL rides."""
    with op.get_context().autocommit_block():
        op.create_index(INDEX, TABLE, ["user_id", "start_date", "id"],
                        postgresql_concurrently=True)


def downgrade():
    """Remove the index without blocking writes to PostgreSQL rides."""
    with op.get_context().autocommit_block():
        op.drop_index(INDEX, table_name=TABLE, postgresql_concurrently=True)
