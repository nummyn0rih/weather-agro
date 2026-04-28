"""Seed crops dictionary. Idempotent — upsert by `name`.

Run: docker compose exec backend python -m app.scripts.seed_crops
"""

import asyncio

import structlog
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.logging import configure_logging
from app.db.models import Crop
from app.db.session import async_session_factory, engine

CROPS: list[dict] = [
    # base_temperature — для расчёта GDD; optimal_temp — справочно.
    {"name": "Томаты", "base_temperature": 10.0, "optimal_temp_min": 18.0, "optimal_temp_max": 26.0},
    {"name": "Огурцы", "base_temperature": 15.0, "optimal_temp_min": 22.0, "optimal_temp_max": 28.0},
    {"name": "Перец", "base_temperature": 13.0, "optimal_temp_min": 20.0, "optimal_temp_max": 28.0},
    {"name": "Кабачки", "base_temperature": 13.0, "optimal_temp_min": 20.0, "optimal_temp_max": 26.0},
    {"name": "Патиссоны", "base_temperature": 13.0, "optimal_temp_min": 18.0, "optimal_temp_max": 26.0},
    {"name": "Лук", "base_temperature": 4.0, "optimal_temp_min": 13.0, "optimal_temp_max": 24.0},
    {"name": "Морковь", "base_temperature": 4.0, "optimal_temp_min": 16.0, "optimal_temp_max": 22.0},
    {"name": "Картофель", "base_temperature": 7.0, "optimal_temp_min": 15.0, "optimal_temp_max": 20.0},
    {"name": "Капуста", "base_temperature": 4.0, "optimal_temp_min": 15.0, "optimal_temp_max": 22.0},
    {"name": "Свёкла", "base_temperature": 5.0, "optimal_temp_min": 16.0, "optimal_temp_max": 22.0},
]


async def seed_crops() -> int:
    log = structlog.get_logger()
    async with async_session_factory() as session:
        for crop in CROPS:
            stmt = pg_insert(Crop).values(**crop)
            stmt = stmt.on_conflict_do_update(
                index_elements=["name"],
                set_={
                    "base_temperature": stmt.excluded.base_temperature,
                    "optimal_temp_min": stmt.excluded.optimal_temp_min,
                    "optimal_temp_max": stmt.excluded.optimal_temp_max,
                },
            )
            await session.execute(stmt)
        await session.commit()
    log.info("crops.seeded", count=len(CROPS))
    return len(CROPS)


async def _main() -> None:
    configure_logging()
    try:
        await seed_crops()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(_main())
