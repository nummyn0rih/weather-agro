"""Tabular export helpers for `weather_daily` query results.

Both formats use the rows returned by ``query_daily``: one record per
(time, location_id) for the selected parameters.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Sequence
from typing import Any

from openpyxl import Workbook


def _header(parameters: Sequence[str]) -> list[str]:
    return ["time", "location_id", "source", *parameters]


def _row_values(row: dict[str, Any], parameters: Sequence[str]) -> list[Any]:
    return [
        row["time"].isoformat(),
        row["location_id"],
        row["source"],
        *(row.get(p) for p in parameters),
    ]


def rows_to_csv(rows: Sequence[dict[str, Any]], parameters: Sequence[str]) -> str:
    """Render rows as CSV text with a header line."""
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(_header(parameters))
    for r in rows:
        writer.writerow(_row_values(r, parameters))
    return buf.getvalue()


def rows_to_xlsx(rows: Sequence[dict[str, Any]], parameters: Sequence[str]) -> bytes:
    """Render rows as an .xlsx workbook (single sheet)."""
    wb = Workbook(write_only=True)
    ws = wb.create_sheet(title="weather")
    ws.append(_header(parameters))
    for r in rows:
        ws.append(_row_values(r, parameters))
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
