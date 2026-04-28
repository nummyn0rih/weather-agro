from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

ImportStatus = str  # 'pending' | 'in_progress' | 'done' | 'error'


class Location(Base):
    __tablename__ = "locations"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    region: Mapped[str | None] = mapped_column(String(100))
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # History import tracking (set by background task)
    import_status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="pending"
    )
    import_progress: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    import_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    import_finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    import_error: Mapped[str | None] = mapped_column(Text)


class LocationCrop(Base):
    __tablename__ = "location_crops"

    location_id: Mapped[int] = mapped_column(
        ForeignKey("locations.id", ondelete="CASCADE"), primary_key=True
    )
    crop_id: Mapped[int] = mapped_column(
        ForeignKey("crops.id", ondelete="RESTRICT"), primary_key=True
    )
    season_year: Mapped[int] = mapped_column(Integer, primary_key=True)
