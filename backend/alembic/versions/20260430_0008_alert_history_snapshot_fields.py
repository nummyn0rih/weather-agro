"""alert_history: snapshot columns + FK ondelete SET NULL

Revision ID: 0008
Revises: 0007
Create Date: 2026-04-30

Two-step within a single migration:
1. add 5 snapshot columns as nullable
2. backfill from alert_rules (existing rules) + placeholders for orphan rows
3. drop+recreate FKs with ON DELETE SET NULL, make rule_id and location_id nullable
4. SET NOT NULL on 4 snapshot columns (threshold_max_snapshot stays nullable)
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Step 1: add snapshot columns nullable
    op.add_column(
        "alert_history",
        sa.Column("rule_name_snapshot", sa.String(200), nullable=True),
    )
    op.add_column(
        "alert_history",
        sa.Column("parameter_snapshot", sa.String(50), nullable=True),
    )
    op.add_column(
        "alert_history",
        sa.Column("condition_snapshot", sa.String(10), nullable=True),
    )
    op.add_column(
        "alert_history",
        sa.Column("threshold_snapshot", sa.Float(), nullable=True),
    )
    op.add_column(
        "alert_history",
        sa.Column("threshold_max_snapshot", sa.Float(), nullable=True),
    )

    # Step 2a: backfill from alert_rules where rule still exists
    op.execute(
        """
        UPDATE alert_history AS ah
        SET
            rule_name_snapshot = ar.name,
            parameter_snapshot = ar.parameter,
            condition_snapshot = ar.condition,
            threshold_snapshot = ar.threshold,
            threshold_max_snapshot = ar.threshold_max
        FROM alert_rules AS ar
        WHERE ah.rule_id = ar.id
          AND ah.rule_name_snapshot IS NULL
        """
    )

    # Step 2b: placeholder backfill for orphan rows (rule already deleted).
    # parameter_snapshot must satisfy AlertParameter Literal in API schema, so we
    # use a legit value ('temperature_avg'); the '(deleted rule)' name signals intent.
    op.execute(
        """
        UPDATE alert_history
        SET
            rule_name_snapshot = '(deleted rule)',
            parameter_snapshot = 'temperature_avg',
            condition_snapshot = 'gt',
            threshold_snapshot = 0
        WHERE rule_name_snapshot IS NULL
        """
    )

    # Step 3: drop+recreate FKs with ON DELETE SET NULL, FK columns become nullable
    op.drop_constraint(
        "alert_history_rule_id_fkey", "alert_history", type_="foreignkey"
    )
    op.drop_constraint(
        "alert_history_location_id_fkey", "alert_history", type_="foreignkey"
    )
    op.alter_column(
        "alert_history",
        "rule_id",
        existing_type=sa.Integer(),
        nullable=True,
    )
    op.alter_column(
        "alert_history",
        "location_id",
        existing_type=sa.Integer(),
        nullable=True,
    )
    op.create_foreign_key(
        "alert_history_rule_id_fkey",
        "alert_history",
        "alert_rules",
        ["rule_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "alert_history_location_id_fkey",
        "alert_history",
        "locations",
        ["location_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Step 4: SET NOT NULL on required snapshot columns (threshold_max stays nullable)
    op.alter_column(
        "alert_history",
        "rule_name_snapshot",
        existing_type=sa.String(200),
        nullable=False,
    )
    op.alter_column(
        "alert_history",
        "parameter_snapshot",
        existing_type=sa.String(50),
        nullable=False,
    )
    op.alter_column(
        "alert_history",
        "condition_snapshot",
        existing_type=sa.String(10),
        nullable=False,
    )
    op.alter_column(
        "alert_history",
        "threshold_snapshot",
        existing_type=sa.Float(),
        nullable=False,
    )


def downgrade() -> None:
    # Safety: original schema requires rule_id/location_id NOT NULL.
    # If history rows exist with NULL FK (rule/location deleted while on this revision),
    # downgrade would silently lose them. Refuse and force operator to act explicitly.
    conn = op.get_bind()
    orphan_count = conn.execute(
        sa.text(
            """
            SELECT COUNT(*) FROM alert_history
            WHERE rule_id IS NULL OR location_id IS NULL
            """
        )
    ).scalar()

    if orphan_count and orphan_count > 0:
        raise RuntimeError(
            f"Cannot downgrade: {orphan_count} alert_history rows have NULL rule_id/location_id. "
            "Original schema requires NOT NULL. To proceed with data loss, manually run: "
            "DELETE FROM alert_history WHERE rule_id IS NULL OR location_id IS NULL; "
            "then re-run alembic downgrade."
        )

    # Reverse FK changes: SET NULL → CASCADE, FK columns back to NOT NULL
    op.drop_constraint(
        "alert_history_location_id_fkey", "alert_history", type_="foreignkey"
    )
    op.drop_constraint(
        "alert_history_rule_id_fkey", "alert_history", type_="foreignkey"
    )
    op.alter_column(
        "alert_history",
        "location_id",
        existing_type=sa.Integer(),
        nullable=False,
    )
    op.alter_column(
        "alert_history",
        "rule_id",
        existing_type=sa.Integer(),
        nullable=False,
    )
    op.create_foreign_key(
        "alert_history_rule_id_fkey",
        "alert_history",
        "alert_rules",
        ["rule_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "alert_history_location_id_fkey",
        "alert_history",
        "locations",
        ["location_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # Drop snapshot columns
    op.drop_column("alert_history", "threshold_max_snapshot")
    op.drop_column("alert_history", "threshold_snapshot")
    op.drop_column("alert_history", "condition_snapshot")
    op.drop_column("alert_history", "parameter_snapshot")
    op.drop_column("alert_history", "rule_name_snapshot")
