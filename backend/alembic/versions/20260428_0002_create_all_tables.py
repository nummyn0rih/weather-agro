"""create all tables and weather hypertables

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-28

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_WEATHER_COLUMNS = [
    sa.Column("temp_min", sa.Float()),
    sa.Column("temp_max", sa.Float()),
    sa.Column("temp_avg", sa.Float()),
    sa.Column("soil_temp_0", sa.Float()),
    sa.Column("soil_temp_7", sa.Float()),
    sa.Column("soil_temp_28", sa.Float()),
    sa.Column("soil_temp_100", sa.Float()),
    sa.Column("dew_point", sa.Float()),
    sa.Column("frost_hours", sa.Integer()),
    sa.Column("humidity_min", sa.Float()),
    sa.Column("humidity_max", sa.Float()),
    sa.Column("humidity_avg", sa.Float()),
    sa.Column("soil_moisture_0_7", sa.Float()),
    sa.Column("soil_moisture_7_28", sa.Float()),
    sa.Column("soil_moisture_28_100", sa.Float()),
    sa.Column("precipitation", sa.Float()),
    sa.Column("et0", sa.Float()),
    sa.Column("solar_radiation", sa.Float()),
    sa.Column("sunshine_hours", sa.Float()),
    sa.Column("wind_speed_avg", sa.Float()),
    sa.Column("wind_speed_max", sa.Float()),
    sa.Column("vpd", sa.Float()),
    sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
]


def _weather_table(name: str) -> None:
    op.create_table(
        name,
        sa.Column("time", sa.Date(), nullable=False),
        sa.Column(
            "location_id",
            sa.Integer(),
            sa.ForeignKey("locations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source", sa.String(30), nullable=False),
        *(c.copy() for c in _WEATHER_COLUMNS),
        sa.PrimaryKeyConstraint("time", "location_id", "source"),
    )


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(50), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("telegram_chat_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "crops",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("base_temperature", sa.Float(), nullable=False),
        sa.Column("optimal_temp_min", sa.Float()),
        sa.Column("optimal_temp_max", sa.Float()),
    )

    op.create_table(
        "locations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("region", sa.String(100)),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("note", sa.Text()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "location_crops",
        sa.Column(
            "location_id",
            sa.Integer(),
            sa.ForeignKey("locations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "crop_id",
            sa.Integer(),
            sa.ForeignKey("crops.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("season_year", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("location_id", "crop_id", "season_year"),
    )

    _weather_table("weather_daily")
    _weather_table("weather_forecast")

    op.create_table(
        "field_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "location_id",
            sa.Integer(),
            sa.ForeignKey("locations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(20), nullable=False),
        sa.Column("event_date", sa.Date(), nullable=False),
        sa.Column(
            "crop_id",
            sa.Integer(),
            sa.ForeignKey("crops.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("variety", sa.String(100)),
        sa.Column("area_hectares", sa.Float()),
        sa.Column("yield_kg", sa.Float()),
        sa.Column("quality_rating", sa.Integer()),
        sa.Column("description", sa.Text()),
        sa.Column(
            "photos",
            JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "alert_rules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("parameter", sa.String(50), nullable=False),
        sa.Column("condition", sa.String(10), nullable=False),
        sa.Column("threshold", sa.Float(), nullable=False),
        sa.Column(
            "location_ids",
            JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("telegram", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "alert_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "rule_id",
            sa.Integer(),
            sa.ForeignKey("alert_rules.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "location_id",
            sa.Integer(),
            sa.ForeignKey("locations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
    )

    op.create_table(
        "settings",
        sa.Column("key", sa.String(100), primary_key=True),
        sa.Column("value", JSONB, nullable=False),
    )

    # Indexes
    op.create_index(
        "ix_weather_daily_location_time", "weather_daily", ["location_id", "time"]
    )
    op.create_index(
        "ix_weather_forecast_location_time",
        "weather_forecast",
        ["location_id", "time"],
    )
    op.create_index(
        "ix_field_events_location_date", "field_events", ["location_id", "event_date"]
    )
    op.create_index("ix_alert_history_triggered", "alert_history", ["triggered_at"])

    # TimescaleDB hypertables (1-month chunks per PRD §6.2).
    op.execute(
        "SELECT create_hypertable('weather_daily', 'time', "
        "chunk_time_interval => INTERVAL '1 month', if_not_exists => TRUE)"
    )
    op.execute(
        "SELECT create_hypertable('weather_forecast', 'time', "
        "chunk_time_interval => INTERVAL '1 month', if_not_exists => TRUE)"
    )


def downgrade() -> None:
    op.drop_index("ix_alert_history_triggered", table_name="alert_history")
    op.drop_index("ix_field_events_location_date", table_name="field_events")
    op.drop_index("ix_weather_forecast_location_time", table_name="weather_forecast")
    op.drop_index("ix_weather_daily_location_time", table_name="weather_daily")

    op.drop_table("settings")
    op.drop_table("alert_history")
    op.drop_table("alert_rules")
    op.drop_table("field_events")
    op.drop_table("weather_forecast")
    op.drop_table("weather_daily")
    op.drop_table("location_crops")
    op.drop_table("locations")
    op.drop_table("crops")
    op.drop_table("users")
