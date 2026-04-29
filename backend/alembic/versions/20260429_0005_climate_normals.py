"""add climate_normals table

Revision ID: 0005
Revises: 0004
Create Date: 2026-04-29

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "climate_normals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "location_id",
            sa.Integer(),
            sa.ForeignKey("locations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("parameter", sa.String(40), nullable=False),
        sa.Column("period", sa.String(10), nullable=False),
        sa.Column("bucket", sa.Integer(), nullable=False),
        sa.Column("mean", sa.Float()),
        sa.Column("std", sa.Float()),
        sa.Column("min", sa.Float()),
        sa.Column("max", sa.Float()),
        sa.Column("count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("year_from", sa.Integer()),
        sa.Column("year_to", sa.Integer()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "location_id",
            "parameter",
            "period",
            "bucket",
            name="uq_climate_normals_loc_param_period_bucket",
        ),
    )
    op.create_index(
        "ix_climate_normals_location_id", "climate_normals", ["location_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_climate_normals_location_id", table_name="climate_normals")
    op.drop_table("climate_normals")
