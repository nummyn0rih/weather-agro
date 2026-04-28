"""Schema-level tests for ORM models. No DB required."""

from app.db import models  # noqa: F401  ← register tables on Base.metadata
from app.db.base import Base


EXPECTED_TABLES = {
    "users",
    "crops",
    "locations",
    "location_crops",
    "weather_daily",
    "weather_forecast",
    "field_events",
    "alert_rules",
    "alert_history",
    "settings",
}


def test_all_expected_tables_registered() -> None:
    actual = set(Base.metadata.tables.keys())
    missing = EXPECTED_TABLES - actual
    assert not missing, f"missing tables: {missing}"


def test_weather_daily_composite_pk() -> None:
    table = Base.metadata.tables["weather_daily"]
    pk_cols = {c.name for c in table.primary_key.columns}
    assert pk_cols == {"time", "location_id", "source"}


def test_weather_forecast_composite_pk() -> None:
    table = Base.metadata.tables["weather_forecast"]
    pk_cols = {c.name for c in table.primary_key.columns}
    assert pk_cols == {"time", "location_id", "source"}


def test_location_crops_composite_pk() -> None:
    table = Base.metadata.tables["location_crops"]
    pk_cols = {c.name for c in table.primary_key.columns}
    assert pk_cols == {"location_id", "crop_id", "season_year"}


def test_weather_daily_has_all_prd_columns() -> None:
    cols = set(Base.metadata.tables["weather_daily"].columns.keys())
    required = {
        "time",
        "location_id",
        "source",
        "temp_min",
        "temp_max",
        "temp_avg",
        "soil_temp_0",
        "soil_temp_7",
        "soil_temp_28",
        "soil_temp_100",
        "dew_point",
        "frost_hours",
        "humidity_min",
        "humidity_max",
        "humidity_avg",
        "soil_moisture_0_7",
        "soil_moisture_7_28",
        "soil_moisture_28_100",
        "precipitation",
        "et0",
        "solar_radiation",
        "sunshine_hours",
        "wind_speed_avg",
        "wind_speed_max",
        "vpd",
        "fetched_at",
    }
    assert required.issubset(cols), f"missing columns: {required - cols}"


def test_field_event_columns() -> None:
    cols = set(Base.metadata.tables["field_events"].columns.keys())
    assert {
        "id",
        "location_id",
        "event_type",
        "event_date",
        "crop_id",
        "variety",
        "area_hectares",
        "yield_kg",
        "quality_rating",
        "description",
        "photos",
        "created_at",
    }.issubset(cols)


def test_seed_crops_data_present() -> None:
    """Sanity-check the canned crop data — base_temperature must be set on every entry."""
    from app.scripts.seed_crops import CROPS

    assert len(CROPS) >= 10
    for crop in CROPS:
        assert "name" in crop
        assert "base_temperature" in crop
        assert isinstance(crop["base_temperature"], float)
        assert crop["base_temperature"] >= 0
