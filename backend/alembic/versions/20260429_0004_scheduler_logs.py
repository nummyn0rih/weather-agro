"""add scheduler_logs table

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-29

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "scheduler_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_id", sa.String(100), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("items_processed", sa.Integer(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_scheduler_logs_job_id", "scheduler_logs", ["job_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_scheduler_logs_job_id", table_name="scheduler_logs")
    op.drop_table("scheduler_logs")
