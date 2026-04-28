from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class _WeatherColumnsMixin:
    """Shared weather columns for both daily (history) and forecast tables."""

    # Temperature
    temp_min: Mapped[float | None] = mapped_column(Float)
    temp_max: Mapped[float | None] = mapped_column(Float)
    temp_avg: Mapped[float | None] = mapped_column(Float)
    soil_temp_0: Mapped[float | None] = mapped_column(Float)
    soil_temp_7: Mapped[float | None] = mapped_column(Float)
    soil_temp_28: Mapped[float | None] = mapped_column(Float)
    soil_temp_100: Mapped[float | None] = mapped_column(Float)
    dew_point: Mapped[float | None] = mapped_column(Float)
    frost_hours: Mapped[int | None] = mapped_column(Integer)

    # Humidity
    humidity_min: Mapped[float | None] = mapped_column(Float)
    humidity_max: Mapped[float | None] = mapped_column(Float)
    humidity_avg: Mapped[float | None] = mapped_column(Float)
    soil_moisture_0_7: Mapped[float | None] = mapped_column(Float)
    soil_moisture_7_28: Mapped[float | None] = mapped_column(Float)
    soil_moisture_28_100: Mapped[float | None] = mapped_column(Float)

    # Precipitation / evapotranspiration
    precipitation: Mapped[float | None] = mapped_column(Float)
    et0: Mapped[float | None] = mapped_column(Float)

    # Solar
    solar_radiation: Mapped[float | None] = mapped_column(Float)
    sunshine_hours: Mapped[float | None] = mapped_column(Float)

    # Wind
    wind_speed_avg: Mapped[float | None] = mapped_column(Float)
    wind_speed_max: Mapped[float | None] = mapped_column(Float)

    # Computed at ingest
    vpd: Mapped[float | None] = mapped_column(Float)

    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class WeatherDaily(_WeatherColumnsMixin, Base):
    """Historical daily weather. TimescaleDB hypertable on `time`."""

    __tablename__ = "weather_daily"

    time: Mapped[date] = mapped_column(Date, primary_key=True)
    location_id: Mapped[int] = mapped_column(
        ForeignKey("locations.id", ondelete="CASCADE"), primary_key=True
    )
    source: Mapped[str] = mapped_column(String(30), primary_key=True)


class WeatherForecast(_WeatherColumnsMixin, Base):
    """Forecast weather. TimescaleDB hypertable on `time`."""

    __tablename__ = "weather_forecast"

    time: Mapped[date] = mapped_column(Date, primary_key=True)
    location_id: Mapped[int] = mapped_column(
        ForeignKey("locations.id", ondelete="CASCADE"), primary_key=True
    )
    source: Mapped[str] = mapped_column(String(30), primary_key=True)
