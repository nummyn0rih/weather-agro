from datetime import datetime

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ClimateNormal(Base):
    """Cached multi-year climate normal for one (location, parameter, period, bucket).

    `period` ∈ {'month', 'week', 'doy'}. `bucket` is the 1-based index inside
    the period (1..12 for month, 1..53 for ISO week, 1..366 for day-of-year).
    Stats are computed from `weather_daily` cross-source averages over all
    years for which any data exists at that location.
    """

    __tablename__ = "climate_normals"

    id: Mapped[int] = mapped_column(primary_key=True)
    location_id: Mapped[int] = mapped_column(
        ForeignKey("locations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    parameter: Mapped[str] = mapped_column(String(40), nullable=False)
    period: Mapped[str] = mapped_column(String(10), nullable=False)
    bucket: Mapped[int] = mapped_column(Integer, nullable=False)

    mean: Mapped[float | None] = mapped_column(Float)
    std: Mapped[float | None] = mapped_column(Float)
    min: Mapped[float | None] = mapped_column(Float)
    max: Mapped[float | None] = mapped_column(Float)
    count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    year_from: Mapped[int | None] = mapped_column(Integer)
    year_to: Mapped[int | None] = mapped_column(Integer)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "location_id",
            "parameter",
            "period",
            "bucket",
            name="uq_climate_normals_loc_param_period_bucket",
        ),
    )
