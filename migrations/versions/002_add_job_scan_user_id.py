"""associate job scans with authenticated users

Revision ID: 002
Revises: 001
"""
from alembic import op
import sqlalchemy as sa


revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("job_scans", sa.Column("user_id", sa.String(), nullable=True))
    op.create_index("ix_job_scans_user_id", "job_scans", ["user_id"])


def downgrade():
    op.drop_index("ix_job_scans_user_id", table_name="job_scans")
    op.drop_column("job_scans", "user_id")
