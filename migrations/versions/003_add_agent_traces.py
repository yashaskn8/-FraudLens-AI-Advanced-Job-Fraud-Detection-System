"""persist evidence-agent audit traces

Revision ID: 003
Revises: 002
"""
from alembic import op
import sqlalchemy as sa


revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "agent_traces",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("scan_id", sa.String(), nullable=False, unique=True),
        sa.Column("tools_called", sa.JSON(), nullable=True),
        sa.Column("tool_results", sa.JSON(), nullable=True),
        sa.Column("reasoning_steps", sa.JSON(), nullable=True),
        sa.Column("critic_passed", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_agent_traces_scan_id", "agent_traces", ["scan_id"])


def downgrade():
    op.drop_index("ix_agent_traces_scan_id", table_name="agent_traces")
    op.drop_table("agent_traces")
