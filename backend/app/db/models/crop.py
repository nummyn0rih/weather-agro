from sqlalchemy import Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Crop(Base):
    __tablename__ = "crops"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    base_temperature: Mapped[float] = mapped_column(Float, nullable=False)
    optimal_temp_min: Mapped[float | None] = mapped_column(Float)
    optimal_temp_max: Mapped[float | None] = mapped_column(Float)
