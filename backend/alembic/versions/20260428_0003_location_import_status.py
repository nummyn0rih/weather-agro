"""add location import status fields

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-28

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "locations",
        sa.Column(
            "import_status",
            sa.String(20),
            nullable=False,
            server_default="pending",
        ),
    )
    op.add_column(
        "locations",
        sa.Column(
            "import_progress",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "locations",
        sa.Column("import_started_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "locations",
        sa.Column("import_finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "locations",
        sa.Column("import_error", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("locations", "import_error")
    op.drop_column("locations", "import_finished_at")
    op.drop_column("locations", "import_started_at")
    op.drop_column("locations", "import_progress")
    op.drop_column("locations", "import_status")
