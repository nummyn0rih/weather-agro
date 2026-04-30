"""PDF report generator (WeasyPrint + Jinja2 + matplotlib).

Generates a season report for one location:
* cover with location/season metadata
* weather summary (means / extrema / sums)
* charts (PNG, embedded as base64)
* anomalies (climate normals)
* field events (planting / harvest / notes)
* yields (per crop)

WeasyPrint and matplotlib are required runtime dependencies. Matplotlib is
used in non-interactive ``Agg`` mode so chart rendering works headless.
"""

from __future__ import annotations

import base64
import io
from collections import defaultdict
from collections.abc import Sequence
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import structlog
from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Crop, FieldEvent, Location
from app.schemas.weather import ALLOWED_PARAMETERS, SUM_PARAMETERS
from app.services.analytics.anomalies import get_anomalies
from app.services.weather.query import query_daily

log = structlog.get_logger()

_TEMPLATES_DIR = Path(__file__).parent / "templates"

_SUMMARY_PARAMETERS: list[tuple[str, str]] = [
    ("temp_avg", "Средняя температура, °C"),
    ("temp_min", "Минимальная температура, °C"),
    ("temp_max", "Максимальная температура, °C"),
    ("humidity_avg", "Влажность воздуха, %"),
    ("precipitation", "Осадки, мм"),
    ("et0", "Эвапотранспирация, мм"),
    ("solar_radiation", "Солнечная радиация, МДж/м²"),
    ("wind_speed_avg", "Скорость ветра, м/с"),
    ("vpd", "VPD, кПа"),
]

_CHART_PARAMETERS: list[tuple[str, str, str]] = [
    ("temp_avg", "Средняя температура, °C", "#d9534f"),
    ("precipitation", "Осадки, мм/день", "#3a7afe"),
    ("humidity_avg", "Влажность воздуха, %", "#5cb85c"),
]

_ANOMALY_PARAMETERS = ("temp_avg", "precipitation")


def _season_bounds(season_year: int) -> tuple[date, date]:
    return date(season_year, 1, 1), date(season_year, 12, 31)


def _summarize(rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Per-parameter aggregates: mean (or None), min, max, optional sum for cumulative ones."""
    out: list[dict[str, Any]] = []
    for key, label in _SUMMARY_PARAMETERS:
        if key not in ALLOWED_PARAMETERS:
            continue
        values: list[float] = []
        for r in rows:
            v = r.get(key)
            if v is None:
                continue
            try:
                values.append(float(v))
            except (TypeError, ValueError):
                continue
        if not values:
            out.append({"label": label, "mean": None, "min": None, "max": None, "sum": None})
            continue
        is_sum = key in SUM_PARAMETERS
        out.append(
            {
                "label": label,
                "mean": round(sum(values) / len(values), 2),
                "min": round(min(values), 2),
                "max": round(max(values), 2),
                "sum": round(sum(values), 2) if is_sum else None,
            }
        )
    return out


def _render_chart(
    rows: Sequence[dict[str, Any]],
    parameter: str,
    title: str,
    color: str,
) -> str | None:
    """Render a parameter time-series chart and return base64-encoded PNG.

    Returns ``None`` if no data points are available.
    """
    points = [(r["time"], r.get(parameter)) for r in rows if r.get(parameter) is not None]
    if not points:
        return None

    # Lazy import: matplotlib pulls in numpy and is heavy.
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    xs = [p[0] for p in points]
    ys = [float(p[1]) for p in points]

    fig, ax = plt.subplots(figsize=(8, 3), dpi=120)
    ax.plot(xs, ys, color=color, linewidth=1.2)
    ax.set_title(title, fontsize=10)
    ax.grid(True, alpha=0.3)
    ax.tick_params(axis="x", labelsize=8)
    ax.tick_params(axis="y", labelsize=8)
    fig.autofmt_xdate()
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode("ascii")


async def _collect_anomalies(
    session: AsyncSession,
    *,
    location_id: int,
    date_from: date,
    date_to: date,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for parameter in _ANOMALY_PARAMETERS:
        try:
            rows = await get_anomalies(
                session,
                location_id=location_id,
                parameter=parameter,
                date_from=date_from,
                date_to=date_to,
            )
        except Exception as exc:
            log.warning(
                "report.anomalies.failed",
                location_id=location_id,
                parameter=parameter,
                error=str(exc),
            )
            continue
        for r in rows:
            if r.get("level") in ("moderate", "extreme"):
                out.append(r)
    out.sort(key=lambda r: (r["time"], r["parameter"]))
    return out


async def _collect_events(
    session: AsyncSession,
    *,
    location_id: int,
    date_from: date,
    date_to: date,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return (events_list, yield_aggregates) for the season."""
    stmt = (
        select(FieldEvent)
        .where(
            FieldEvent.location_id == location_id,
            FieldEvent.event_date >= date_from,
            FieldEvent.event_date <= date_to,
        )
        .order_by(FieldEvent.event_date.asc(), FieldEvent.id.asc())
    )
    result = await session.execute(stmt)
    events = list(result.scalars().all())

    crop_ids = {e.crop_id for e in events if e.crop_id is not None}
    crop_names: dict[int, str] = {}
    if crop_ids:
        crop_rows = await session.execute(select(Crop).where(Crop.id.in_(crop_ids)))
        crop_names = {c.id: c.name for c in crop_rows.scalars().all()}

    events_view = [
        {
            "event_date": e.event_date.isoformat(),
            "event_type": e.event_type,
            "crop_name": crop_names.get(e.crop_id) if e.crop_id else None,
            "area_hectares": e.area_hectares,
            "yield_kg": e.yield_kg,
            "description": e.description,
        }
        for e in events
    ]

    by_crop: dict[int, dict[str, float | None]] = defaultdict(
        lambda: {"yield_kg": 0.0, "area_hectares": None}
    )
    for e in events:
        if e.event_type != "harvest" or e.crop_id is None or e.yield_kg is None:
            continue
        agg = by_crop[e.crop_id]
        agg["yield_kg"] = (agg["yield_kg"] or 0.0) + float(e.yield_kg)
        if e.area_hectares is not None:
            agg["area_hectares"] = (agg["area_hectares"] or 0.0) + float(e.area_hectares)

    yields_view = []
    for crop_id, agg in by_crop.items():
        area = agg["area_hectares"]
        yield_per_ha = (agg["yield_kg"] / area) if (area and area > 0) else None
        yields_view.append(
            {
                "crop_name": crop_names.get(crop_id, f"#{crop_id}"),
                "yield_kg": round(agg["yield_kg"] or 0.0, 1),
                "area_hectares": area,
                "yield_per_ha": yield_per_ha,
            }
        )
    yields_view.sort(key=lambda r: r["crop_name"])
    return events_view, yields_view


async def build_report_html(
    session: AsyncSession,
    *,
    location: Location,
    season_year: int,
) -> str:
    """Assemble all sections, render the Jinja2 template, return HTML."""
    date_from, date_to = _season_bounds(season_year)

    weather_rows = await query_daily(
        session,
        location_ids=[location.id],
        parameters=sorted(ALLOWED_PARAMETERS),
        date_from=date_from,
        date_to=date_to,
        source="average",
        aggregation="day",
    )

    summary = _summarize(weather_rows)
    charts: list[dict[str, str]] = []
    for key, title, color in _CHART_PARAMETERS:
        png_b64 = _render_chart(weather_rows, key, title, color)
        if png_b64:
            charts.append({"title": title, "png_b64": png_b64})

    anomalies = await _collect_anomalies(
        session,
        location_id=location.id,
        date_from=date_from,
        date_to=date_to,
    )
    events, yields = await _collect_events(
        session,
        location_id=location.id,
        date_from=date_from,
        date_to=date_to,
    )

    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATES_DIR)),
        autoescape=select_autoescape(["html"]),
    )
    template = env.get_template("season_report.html")
    return template.render(
        location=location,
        season_year=season_year,
        period_from=date_from.isoformat(),
        period_to=date_to.isoformat(),
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        summary=summary,
        charts=charts,
        anomalies=anomalies,
        events=events,
        yields=yields,
    )


def render_pdf(html: str, output_path: Path) -> int:
    """Render HTML → PDF on disk. Returns file size in bytes."""
    # Lazy import: WeasyPrint requires native libs and is slow to import.
    from weasyprint import HTML

    output_path.parent.mkdir(parents=True, exist_ok=True)
    HTML(string=html).write_pdf(str(output_path))
    return output_path.stat().st_size


async def generate_season_report(
    session: AsyncSession,
    *,
    location: Location,
    season_year: int,
    output_path: Path,
) -> int:
    """High-level entry point: build HTML and render to ``output_path``."""
    log.info(
        "report.generate.start",
        location_id=location.id,
        season_year=season_year,
        path=str(output_path),
    )
    html = await build_report_html(
        session, location=location, season_year=season_year
    )
    size = render_pdf(html, output_path)
    log.info(
        "report.generate.done",
        location_id=location.id,
        season_year=season_year,
        path=str(output_path),
        bytes=size,
    )
    return size
