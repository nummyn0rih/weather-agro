"""add threshold_max to alert_rules

Revision ID: 0006
Revises: 0005
Create Date: 2026-04-29

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "alert_rules",
        sa.Column("threshold_max", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("alert_rules", "threshold_max")
