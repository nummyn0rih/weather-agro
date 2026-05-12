from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class BackupLog(Base):
    """Execution log for database backup runs (task 6.2).

    One row per backup run (manual or scheduled). ``status`` is
    ``'success'`` or ``'error'``; ``kind`` is ``'manual'`` or ``'scheduled'``;
    ``filename`` is the remote object name on Yandex.Disk (relative to the
    backup root) when the upload succeeded.
    """

    __tablename__ = "backup_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    filename: Mapped[str | None] = mapped_column(String(255))
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    error: Mapped[str | None] = mapped_column(Text)
