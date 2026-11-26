"""Persist activity jobs and transactional snapshot invalidation."""

from alembic import op
import sqlalchemy as sa

revision = "e1322af018c9"
down_revision = "c4a8d1e7b920"
branch_labels = None
depends_on = None


def upgrade():
    """Create durable jobs and track mutations from ORM and SQL writers."""
    op.create_table(
        "activity_sync_job",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("vc_user.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("from_epoch", sa.BigInteger(), nullable=False),
        sa.Column("to_epoch", sa.BigInteger(), nullable=False),
        sa.Column("page", sa.Integer(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("next_attempt", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revision", sa.BigInteger(), nullable=False),
        sa.Column("recent_watermark", sa.BigInteger()),
        sa.Column("error", sa.String(24)),
    )
    op.create_index("ix_activity_sync_due", "activity_sync_job", ["status", "next_attempt"])
    op.create_table(
        "activity_snapshot_work",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("vc_user.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("generation", sa.BigInteger(), nullable=False),
        sa.Column("published", sa.BigInteger(), nullable=False),
        sa.Column("digest", sa.String(64)),
        sa.Column("next_attempt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.execute("""
        CREATE FUNCTION mark_activity_snapshot(owner_id integer) RETURNS void
        LANGUAGE SQL AS $$
            INSERT INTO activity_snapshot_work (user_id, generation, published, next_attempt)
            VALUES (owner_id, 1, 0, now())
            ON CONFLICT (user_id) DO UPDATE
                SET generation = activity_snapshot_work.generation + 1, next_attempt = now()
        $$;
        CREATE FUNCTION activity_snapshot_dirty() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_TABLE_NAME = 'vc_user' THEN
                PERFORM mark_activity_snapshot(NEW.id);
            ELSIF TG_OP = 'DELETE' THEN
                PERFORM mark_activity_snapshot(OLD.user_id);
            ELSE
                IF TG_OP = 'UPDATE' AND OLD.user_id IS DISTINCT FROM NEW.user_id THEN
                    PERFORM mark_activity_snapshot(OLD.user_id);
                END IF;
                PERFORM mark_activity_snapshot(NEW.user_id);
            END IF;
            RETURN NULL;
        END;
        $$;
        CREATE TRIGGER snapshot_activity_insert_delete AFTER INSERT OR DELETE ON vc_strava_activity
            FOR EACH ROW EXECUTE FUNCTION activity_snapshot_dirty();
        CREATE TRIGGER snapshot_activity_update AFTER UPDATE ON vc_strava_activity
            FOR EACH ROW WHEN (OLD.* IS DISTINCT FROM NEW.*) EXECUTE FUNCTION activity_snapshot_dirty();
        CREATE TRIGGER snapshot_user_insert AFTER INSERT ON vc_user
            FOR EACH ROW EXECUTE FUNCTION activity_snapshot_dirty();
        CREATE TRIGGER snapshot_membership_update AFTER UPDATE OF membership_type ON vc_user
            FOR EACH ROW WHEN (OLD.membership_type IS DISTINCT FROM NEW.membership_type)
            EXECUTE FUNCTION activity_snapshot_dirty();
    """)


def downgrade():
    """Remove new triggers and queues while preserving rides and users."""
    op.execute("""
        DROP TRIGGER snapshot_membership_update ON vc_user;
        DROP TRIGGER snapshot_user_insert ON vc_user;
        DROP TRIGGER snapshot_activity_update ON vc_strava_activity;
        DROP TRIGGER snapshot_activity_insert_delete ON vc_strava_activity;
        DROP FUNCTION activity_snapshot_dirty();
        DROP FUNCTION mark_activity_snapshot(integer);
    """)
    op.drop_table("activity_snapshot_work")
    op.drop_table("activity_sync_job")
