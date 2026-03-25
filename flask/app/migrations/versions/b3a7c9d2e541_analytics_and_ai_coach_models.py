"""analytics and ai_coach models

Revision ID: b3a7c9d2e541
Revises: 1f8679617316
Create Date: 2026-03-25 08:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'b3a7c9d2e541'
down_revision = '1f8679617316'
branch_labels = None
depends_on = None


def upgrade():
    # Remove analytics fields from vc_strava_activity
    with op.batch_alter_table('vc_strava_activity', schema=None) as batch_op:
        batch_op.drop_column('identification_data')
        batch_op.drop_column('assessment_data')
        batch_op.drop_column('confirmed_type')
        batch_op.drop_column('classification_source')
        batch_op.drop_column('power_curve_data')
        batch_op.drop_column('time_in_zones')

    # Create vc_activity_analytics
    op.create_table(
        'vc_activity_analytics',
        sa.Column('id',                  sa.Integer(),    nullable=False),
        sa.Column('activity_id',         sa.BigInteger(), nullable=False),
        sa.Column('user_id',             sa.Integer(),    nullable=False),
        sa.Column('classification_data', sa.Text(),       nullable=True),
        sa.Column('execution_data',      sa.Text(),       nullable=True),
        sa.Column('power_curve_data',    sa.Text(),       nullable=True),
        sa.Column('time_in_zones',       sa.Text(),       nullable=True),
        sa.ForeignKeyConstraint(['activity_id'], ['vc_strava_activity.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'],     ['vc_user.id'],            ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('activity_id'),
    )

    # Create vc_activity_insight
    op.create_table(
        'vc_activity_insight',
        sa.Column('id',           sa.Integer(),     nullable=False),
        sa.Column('activity_id',  sa.BigInteger(),  nullable=False),
        sa.Column('user_id',      sa.Integer(),     nullable=False),
        sa.Column('insight_type', sa.String(32),    nullable=False),
        sa.Column('coach_insight',sa.Text(),        nullable=True),
        sa.Column('created_at',   sa.DateTime(),    server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['activity_id'], ['vc_strava_activity.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'],     ['vc_user.id'],            ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade():
    op.drop_table('vc_activity_insight')
    op.drop_table('vc_activity_analytics')

    with op.batch_alter_table('vc_strava_activity', schema=None) as batch_op:
        batch_op.add_column(sa.Column('time_in_zones',       sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('power_curve_data',    sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('classification_source', sa.String(16), nullable=True))
        batch_op.add_column(sa.Column('confirmed_type',      sa.String(32), nullable=True))
        batch_op.add_column(sa.Column('assessment_data',     sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('identification_data', sa.Text(), nullable=True))
