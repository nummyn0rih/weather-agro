"""add is_admin / is_active to users + backfill

Revision ID: 0010
Revises: 0009
Create Date: 2026-05-04

"""
import os
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "is_admin",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )

    # Backfill: existing rows already get FALSE/TRUE via server_default.
    # Promote ADMIN_USERNAME (if set) to is_admin=true.
    admin_username = os.getenv("ADMIN_USERNAME")
    if admin_username:
        op.execute(
            sa.text("UPDATE users SET is_admin = TRUE WHERE username = :u").bindparams(
                u=admin_username
            )
        )

    # Ensure is_active=true on every existing row (defensive — server_default
    # already covers new rows; explicit for legacy rows that pre-date this col).
    op.execute(sa.text("UPDATE users SET is_active = TRUE WHERE is_active = FALSE"))


def downgrade() -> None:
    op.drop_column("users", "is_active")
    op.drop_column("users", "is_admin")
