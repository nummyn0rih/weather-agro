"""add telegram bind code fields to users

Revision ID: 0007
Revises: 0006
Create Date: 2026-04-30

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("telegram_bind_code", sa.String(16), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column(
            "telegram_bind_code_expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_users_telegram_bind_code",
        "users",
        ["telegram_bind_code"],
        unique=True,
    )
    op.create_index(
        "ix_users_telegram_chat_id",
        "users",
        ["telegram_chat_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_users_telegram_chat_id", table_name="users")
    op.drop_index("ix_users_telegram_bind_code", table_name="users")
    op.drop_column("users", "telegram_bind_code_expires_at")
    op.drop_column("users", "telegram_bind_code")
