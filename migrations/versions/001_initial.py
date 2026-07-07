"""initial migration

Revision ID: 001
Revises:
Create Date: 2024-01-01
"""
from alembic import op
import sqlalchemy as sa

revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'job_scans',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('url', sa.String(), nullable=True),
        sa.Column('job_title', sa.String(), nullable=True),
        sa.Column('company_name', sa.String(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('trust_score', sa.Integer(), nullable=False),
        sa.Column('verdict', sa.String(), nullable=False),
        sa.Column('flags', sa.JSON(), default=list),
        sa.Column('signal_scores', sa.JSON(), default=dict),
        sa.Column('explanation', sa.Text(), nullable=True),
        sa.Column('is_confirmed_fraud', sa.Integer(), default=0),
        sa.Column('report_count', sa.Integer(), default=0),
        sa.Column('created_at', sa.DateTime()),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'fraud_reports',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('scan_id', sa.String(), nullable=False),
        sa.Column('reporter_ip', sa.String(), nullable=True),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('confirmed', sa.Integer(), default=0),
        sa.Column('created_at', sa.DateTime()),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade():
    op.drop_table('fraud_reports')
    op.drop_table('job_scans')
