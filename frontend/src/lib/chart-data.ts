import type {
  CumulativePoint,
  WeatherDailyPoint,
} from '@/lib/weather-api';

export type ChartType =
  | 'timeseries'
  | 'compare_locations'
  | 'overlay_years'
  | 'cumulative'
  | 'heatmap'
  | 'correlations';

export interface PivotedRow {
  time: string;
  [series: string]: string | number | null;
}

export interface SeriesDef {
  key: string;
  label: string;
  color: string;
}

const PALETTE = [
  '#2563eb',
  '#16a34a',
  '#dc2626',
  '#9333ea',
  '#ea580c',
  '#0891b2',
  '#be185d',
  '#65a30d',
  '#7c3aed',
  '#0ea5e9',
];

export function pickColor(index: number): string {
  return PALETTE[index % PALETTE.length] ?? '#2563eb';
}

function asNumber(value: string | number | null | undefined): number | null {
  if (value === null || value === undefined) return null;
  if (typeof value === 'number') return value;
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

interface LocationLookup {
  byId: Map<number, string>;
}

export function makeLocationLookup(
  locations: { id: number; name: string }[],
): LocationLookup {
  return {
    byId: new Map(locations.map((l) => [l.id, l.name])),
  };
}

export function pivotTimeseries(
  rows: WeatherDailyPoint[],
  parameters: string[],
  locations: LocationLookup,
): { data: PivotedRow[]; series: SeriesDef[] } {
  const byTime = new Map<string, PivotedRow>();
  const seenSeries = new Map<string, SeriesDef>();

  for (const row of rows) {
    const time = row.time;
    let bucket = byTime.get(time);
    if (!bucket) {
      bucket = { time };
      byTime.set(time, bucket);
    }
    const locName =
      locations.byId.get(row.location_id) ?? `#${row.location_id}`;
    for (const param of parameters) {
      const seriesKey = `${locName} · ${param}`;
      bucket[seriesKey] = asNumber(row[param]);
      if (!seenSeries.has(seriesKey)) {
        seenSeries.set(seriesKey, {
          key: seriesKey,
          label: seriesKey,
          color: pickColor(seenSeries.size),
        });
      }
    }
  }

  const data = [...byTime.values()].sort((a, b) => a.time.localeCompare(b.time));
  return { data, series: [...seenSeries.values()] };
}

export function pivotCompareLocations(
  rows: WeatherDailyPoint[],
  parameter: string,
  locations: LocationLookup,
): { data: PivotedRow[]; series: SeriesDef[] } {
  const byTime = new Map<string, PivotedRow>();
  const seenSeries = new Map<string, SeriesDef>();

  for (const row of rows) {
    const time = row.time;
    let bucket = byTime.get(time);
    if (!bucket) {
      bucket = { time };
      byTime.set(time, bucket);
    }
    const seriesKey =
      locations.byId.get(row.location_id) ?? `#${row.location_id}`;
    bucket[seriesKey] = asNumber(row[parameter]);
    if (!seenSeries.has(seriesKey)) {
      seenSeries.set(seriesKey, {
        key: seriesKey,
        label: seriesKey,
        color: pickColor(seenSeries.size),
      });
    }
  }

  const data = [...byTime.values()].sort((a, b) => a.time.localeCompare(b.time));
  return { data, series: [...seenSeries.values()] };
}

export function pivotOverlayYears(
  rows: WeatherDailyPoint[],
  parameter: string,
): { data: PivotedRow[]; series: SeriesDef[] } {
  const byMmDd = new Map<string, PivotedRow>();
  const seenSeries = new Map<string, SeriesDef>();

  for (const row of rows) {
    const mmDd = row.time.slice(5);
    let bucket = byMmDd.get(mmDd);
    if (!bucket) {
      bucket = { time: mmDd };
      byMmDd.set(mmDd, bucket);
    }
    const yearRaw = row['year'];
    const year =
      typeof yearRaw === 'number' ? yearRaw : Number(row.time.slice(0, 4));
    const seriesKey = String(year);
    bucket[seriesKey] = asNumber(row[parameter]);
    if (!seenSeries.has(seriesKey)) {
      seenSeries.set(seriesKey, {
        key: seriesKey,
        label: seriesKey,
        color: pickColor(seenSeries.size),
      });
    }
  }

  const data = [...byMmDd.values()].sort((a, b) => a.time.localeCompare(b.time));
  return { data, series: [...seenSeries.values()] };
}

export function pivotCumulative(
  rows: CumulativePoint[],
  locations: LocationLookup,
): { data: PivotedRow[]; series: SeriesDef[] } {
  const byTime = new Map<string, PivotedRow>();
  const seenSeries = new Map<string, SeriesDef>();

  for (const row of rows) {
    const time = row.time;
    let bucket = byTime.get(time);
    if (!bucket) {
      bucket = { time };
      byTime.set(time, bucket);
    }
    const seriesKey =
      locations.byId.get(row.location_id) ?? `#${row.location_id}`;
    bucket[seriesKey] = row.cumulative;
    if (!seenSeries.has(seriesKey)) {
      seenSeries.set(seriesKey, {
        key: seriesKey,
        label: seriesKey,
        color: pickColor(seenSeries.size),
      });
    }
  }

  const data = [...byTime.values()].sort((a, b) => a.time.localeCompare(b.time));
  return { data, series: [...seenSeries.values()] };
}
