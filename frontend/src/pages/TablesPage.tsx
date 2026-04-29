import { useQuery } from '@tanstack/react-query';
import axios from 'axios';
import { Download, Loader2, Save, Trash2 } from 'lucide-react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';

import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { downloadString, rowsToCsv } from '@/lib/chart-export';
import { listLocations, type Location } from '@/lib/locations-api';
import {
  type StatsAggregation,
  type WeatherSource,
  type WeatherStatsRow,
  WEATHER_PARAMETERS,
  getWeatherStats,
} from '@/lib/weather-api';

type Metric = 'min' | 'max' | 'mean' | 'sum' | 'count';
type PeriodPreset = '7d' | '30d' | '90d' | '365d' | 'ytd' | 'custom';
type SortDir = 'asc' | 'desc';
type SortKey =
  | 'time'
  | 'location'
  | 'parameter'
  | 'min'
  | 'max'
  | 'mean'
  | 'sum'
  | 'count';

interface SortState {
  key: SortKey;
  dir: SortDir;
}

interface TableFilters {
  locationIds: number[];
  parameters: string[];
  period: PeriodPreset;
  customFrom: string;
  customTo: string;
  source: WeatherSource;
  aggregation: StatsAggregation;
  metric: Metric;
}

interface TablePreset {
  name: string;
  filters: TableFilters;
  savedAt: string;
}

const PRESETS_KEY = 'weather-agro:tables:presets';

const SOURCES: { value: WeatherSource; label: string }[] = [
  { value: 'average', label: 'Среднее по источникам' },
  { value: 'open_meteo', label: 'Open-Meteo' },
  { value: 'nasa_power', label: 'NASA POWER' },
  { value: 'openweathermap', label: 'OpenWeatherMap' },
];

const PERIOD_PRESETS: { value: PeriodPreset; label: string }[] = [
  { value: '7d', label: '7 дней' },
  { value: '30d', label: '30 дней' },
  { value: '90d', label: '90 дней' },
  { value: '365d', label: 'Год' },
  { value: 'ytd', label: 'С начала года' },
  { value: 'custom', label: 'Произвольный' },
];

const AGGREGATIONS: { value: StatsAggregation; label: string }[] = [
  { value: 'day', label: 'День' },
  { value: 'week', label: 'Неделя' },
  { value: 'month', label: 'Месяц' },
  { value: 'season', label: 'Сезон' },
  { value: 'year', label: 'Год' },
  { value: 'total', label: 'Всего' },
];

const METRICS: { value: Metric; label: string }[] = [
  { value: 'mean', label: 'Среднее' },
  { value: 'min', label: 'Минимум' },
  { value: 'max', label: 'Максимум' },
  { value: 'sum', label: 'Сумма' },
  { value: 'count', label: 'Количество' },
];

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

function addDaysIso(iso: string, days: number): string {
  const d = new Date(`${iso}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}

function startOfYearIso(): string {
  const d = new Date();
  return `${d.getUTCFullYear()}-01-01`;
}

function resolvePeriod(
  preset: PeriodPreset,
  customFrom: string,
  customTo: string,
): { date_from: string; date_to: string } {
  const today = todayIso();
  switch (preset) {
    case '7d':
      return { date_from: addDaysIso(today, -6), date_to: today };
    case '30d':
      return { date_from: addDaysIso(today, -29), date_to: today };
    case '90d':
      return { date_from: addDaysIso(today, -89), date_to: today };
    case '365d':
      return { date_from: addDaysIso(today, -364), date_to: today };
    case 'ytd':
      return { date_from: startOfYearIso(), date_to: today };
    case 'custom':
      return { date_from: customFrom, date_to: customTo };
  }
}

function parseCsvNumbers(value: string | null): number[] {
  if (!value) return [];
  return value
    .split(',')
    .map((v) => Number(v.trim()))
    .filter((n) => Number.isFinite(n));
}

function parseCsvStrings(value: string | null): string[] {
  if (!value) return [];
  return value
    .split(',')
    .map((v) => v.trim())
    .filter(Boolean);
}

function getErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data as { detail?: string } | undefined;
    if (typeof data?.detail === 'string') return data.detail;
    return error.message;
  }
  return error instanceof Error ? error.message : 'Неизвестная ошибка';
}

function readFilters(params: URLSearchParams): TableFilters {
  const today = todayIso();
  return {
    locationIds: parseCsvNumbers(params.get('locations')),
    parameters: parseCsvStrings(params.get('parameters')),
    period: (params.get('period') ?? '30d') as PeriodPreset,
    customFrom: params.get('from') ?? addDaysIso(today, -29),
    customTo: params.get('to') ?? today,
    source: (params.get('source') ?? 'average') as WeatherSource,
    aggregation: (params.get('agg') ?? 'month') as StatsAggregation,
    metric: (params.get('metric') ?? 'mean') as Metric,
  };
}

function writeFilters(filters: TableFilters): URLSearchParams {
  const next = new URLSearchParams();
  next.set('period', filters.period);
  next.set('source', filters.source);
  next.set('agg', filters.aggregation);
  next.set('metric', filters.metric);
  if (filters.locationIds.length > 0) {
    next.set('locations', filters.locationIds.join(','));
  }
  if (filters.parameters.length > 0) {
    next.set('parameters', filters.parameters.join(','));
  }
  if (filters.period === 'custom') {
    next.set('from', filters.customFrom);
    next.set('to', filters.customTo);
  }
  return next;
}

function formatNumber(n: number | null, fractionDigits = 2): string {
  if (n === null || n === undefined || !Number.isFinite(n)) return '';
  return n.toFixed(fractionDigits);
}

function formatBucket(time: string, agg: StatsAggregation): string {
  if (agg === 'total') return 'Всего';
  if (!time) return '';
  if (agg === 'year') return time.slice(0, 4);
  if (agg === 'month') return time.slice(0, 7);
  if (agg === 'season') {
    const month = Number(time.slice(5, 7));
    const year = time.slice(0, 4);
    if (month === 12 || month <= 2) return `${year} зима`;
    if (month <= 5) return `${year} весна`;
    if (month <= 8) return `${year} лето`;
    return `${year} осень`;
  }
  return time.slice(0, 10);
}

function readPresets(): TablePreset[] {
  try {
    const raw = localStorage.getItem(PRESETS_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(
      (p): p is TablePreset =>
        typeof p === 'object' &&
        p !== null &&
        typeof (p as TablePreset).name === 'string' &&
        typeof (p as TablePreset).filters === 'object',
    );
  } catch {
    return [];
  }
}

function writePresets(presets: TablePreset[]): void {
  localStorage.setItem(PRESETS_KEY, JSON.stringify(presets));
}

function lerpColor(t: number): string {
  const clamped = Math.max(0, Math.min(1, t));
  const r = Math.round(59 + (239 - 59) * clamped);
  const g = Math.round(130 + (68 - 130) * clamped);
  const b = Math.round(246 + (68 - 246) * clamped);
  return `rgba(${r}, ${g}, ${b}, 0.18)`;
}

function colorForCell(
  value: number | null,
  scale: { min: number; max: number } | undefined,
): string | undefined {
  if (value === null || !Number.isFinite(value) || !scale) return undefined;
  if (scale.max === scale.min) return lerpColor(0.5);
  return lerpColor((value - scale.min) / (scale.max - scale.min));
}

interface DisplayRow {
  key: string;
  bucket: string;
  bucketRaw: string;
  locationId: number;
  locationName: string;
  parameter: string;
  min: number | null;
  max: number | null;
  mean: number | null;
  sum: number | null;
  count: number;
}

function buildDisplayRows(
  rows: WeatherStatsRow[],
  locationNameById: Map<number, string>,
  agg: StatsAggregation,
): DisplayRow[] {
  return rows.map((r) => ({
    key: `${r.time}|${r.location_id}|${r.parameter}|${r.source}`,
    bucket: formatBucket(r.time, agg),
    bucketRaw: r.time,
    locationId: r.location_id,
    locationName: locationNameById.get(r.location_id) ?? `#${r.location_id}`,
    parameter: r.parameter,
    min: r.min,
    max: r.max,
    mean: r.mean,
    sum: r.sum,
    count: r.count,
  }));
}

function compareRows(a: DisplayRow, b: DisplayRow, sort: SortState): number {
  const dir = sort.dir === 'asc' ? 1 : -1;
  switch (sort.key) {
    case 'time':
      return a.bucketRaw.localeCompare(b.bucketRaw) * dir;
    case 'location':
      return a.locationName.localeCompare(b.locationName, 'ru') * dir;
    case 'parameter':
      return a.parameter.localeCompare(b.parameter) * dir;
    default: {
      const av = a[sort.key];
      const bv = b[sort.key];
      if (av === null && bv === null) return 0;
      if (av === null) return 1;
      if (bv === null) return -1;
      return (av - bv) * dir;
    }
  }
}

function applyFilters(
  rows: DisplayRow[],
  textFilter: string,
  metric: Metric,
  metricMin: string,
  metricMax: string,
): DisplayRow[] {
  const text = textFilter.trim().toLowerCase();
  const lo = metricMin === '' ? null : Number(metricMin);
  const hi = metricMax === '' ? null : Number(metricMax);
  return rows.filter((row) => {
    if (text) {
      const hay = `${row.bucket} ${row.locationName} ${row.parameter}`.toLowerCase();
      if (!hay.includes(text)) return false;
    }
    const value = row[metric];
    if (lo !== null && Number.isFinite(lo)) {
      if (value === null || value < lo) return false;
    }
    if (hi !== null && Number.isFinite(hi)) {
      if (value === null || value > hi) return false;
    }
    return true;
  });
}

function buildScalesByParameter(
  rows: DisplayRow[],
  metric: Metric,
): Map<string, { min: number; max: number }> {
  const map = new Map<string, { min: number; max: number }>();
  for (const row of rows) {
    const v = row[metric];
    if (v === null || !Number.isFinite(v)) continue;
    const cur = map.get(row.parameter);
    if (!cur) {
      map.set(row.parameter, { min: v, max: v });
    } else {
      if (v < cur.min) cur.min = v;
      if (v > cur.max) cur.max = v;
    }
  }
  return map;
}

function rowsForExport(rows: DisplayRow[]): Record<string, unknown>[] {
  return rows.map((r) => ({
    period: r.bucket,
    location: r.locationName,
    parameter: r.parameter,
    min: r.min,
    max: r.max,
    mean: r.mean,
    sum: r.sum,
    count: r.count,
  }));
}

const EXPORT_COLUMNS = [
  'period',
  'location',
  'parameter',
  'min',
  'max',
  'mean',
  'sum',
  'count',
];

function rowsToSpreadsheetXml(
  rows: Record<string, unknown>[],
  columns: string[],
): string {
  const escapeXml = (s: string): string =>
    s
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  const header = columns
    .map(
      (c) =>
        `<Cell><Data ss:Type="String">${escapeXml(c)}</Data></Cell>`,
    )
    .join('');
  const body = rows
    .map((row) => {
      const cells = columns
        .map((col) => {
          const v = row[col];
          if (v === null || v === undefined || v === '') {
            return '<Cell><Data ss:Type="String"></Data></Cell>';
          }
          if (typeof v === 'number' && Number.isFinite(v)) {
            return `<Cell><Data ss:Type="Number">${v}</Data></Cell>`;
          }
          if (typeof v === 'boolean') {
            return `<Cell><Data ss:Type="String">${v ? 'true' : 'false'}</Data></Cell>`;
          }
          if (typeof v !== 'string') {
            return '<Cell><Data ss:Type="String"></Data></Cell>';
          }
          return `<Cell><Data ss:Type="String">${escapeXml(v)}</Data></Cell>`;
        })
        .join('');
      return `<Row>${cells}</Row>`;
    })
    .join('');
  return `<?xml version="1.0" encoding="UTF-8"?>
<?mso-application progid="Excel.Sheet"?>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"
 xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">
 <Worksheet ss:Name="Stats">
  <Table>
   <Row>${header}</Row>
   ${body}
  </Table>
 </Worksheet>
</Workbook>`;
}

export function TablesPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const filters = useMemo(() => readFilters(searchParams), [searchParams]);

  const updateFilters = useCallback(
    (patch: Partial<TableFilters>) => {
      const next = { ...filters, ...patch };
      setSearchParams(writeFilters(next), { replace: true });
    },
    [filters, setSearchParams],
  );

  const [sort, setSort] = useState<SortState>({ key: 'time', dir: 'asc' });
  const [textFilter, setTextFilter] = useState('');
  const [metricMin, setMetricMin] = useState('');
  const [metricMax, setMetricMax] = useState('');
  const [presets, setPresets] = useState<TablePreset[]>(() => readPresets());
  const [presetName, setPresetName] = useState('');

  const locationsQuery = useQuery<Location[], Error>({
    queryKey: ['locations'],
    queryFn: () => listLocations(),
  });

  const locationNameById = useMemo(() => {
    const map = new Map<number, string>();
    for (const l of locationsQuery.data ?? []) map.set(l.id, l.name);
    return map;
  }, [locationsQuery.data]);

  const sortedLocations = useMemo(
    () =>
      [...(locationsQuery.data ?? [])].sort((a, b) =>
        a.name.localeCompare(b.name, 'ru'),
      ),
    [locationsQuery.data],
  );

  const period = resolvePeriod(filters.period, filters.customFrom, filters.customTo);

  const queryEnabled =
    filters.locationIds.length > 0 && filters.parameters.length > 0;

  const statsQuery = useQuery<WeatherStatsRow[], Error>({
    queryKey: [
      'weather-stats',
      filters.locationIds,
      filters.parameters,
      period,
      filters.source,
      filters.aggregation,
    ],
    queryFn: () =>
      getWeatherStats({
        location_ids: filters.locationIds,
        parameters: filters.parameters,
        date_from: period.date_from,
        date_to: period.date_to,
        source: filters.source,
        aggregation: filters.aggregation,
      }),
    enabled: queryEnabled,
  });

  const displayRows = useMemo(
    () =>
      buildDisplayRows(
        statsQuery.data ?? [],
        locationNameById,
        filters.aggregation,
      ),
    [statsQuery.data, locationNameById, filters.aggregation],
  );

  const filteredRows = useMemo(
    () => applyFilters(displayRows, textFilter, filters.metric, metricMin, metricMax),
    [displayRows, textFilter, filters.metric, metricMin, metricMax],
  );

  const sortedRows = useMemo(() => {
    const out = [...filteredRows];
    out.sort((a, b) => compareRows(a, b, sort));
    return out;
  }, [filteredRows, sort]);

  const scalesByParameter = useMemo(
    () => buildScalesByParameter(filteredRows, filters.metric),
    [filteredRows, filters.metric],
  );

  const toggleSort = (key: SortKey) => {
    setSort((prev) => {
      if (prev.key === key) {
        return { key, dir: prev.dir === 'asc' ? 'desc' : 'asc' };
      }
      return { key, dir: 'asc' };
    });
  };

  const toggleLocation = (id: number) => {
    const present = filters.locationIds.includes(id);
    updateFilters({
      locationIds: present
        ? filters.locationIds.filter((v) => v !== id)
        : [...filters.locationIds, id],
    });
  };

  const toggleParameter = (p: string) => {
    const present = filters.parameters.includes(p);
    updateFilters({
      parameters: present
        ? filters.parameters.filter((v) => v !== p)
        : [...filters.parameters, p],
    });
  };

  const filenameBase = `tables_${filters.aggregation}_${period.date_from}_${period.date_to}`;

  const handleExportCsv = () => {
    const csv = '\uFEFF' + rowsToCsv(rowsForExport(sortedRows), EXPORT_COLUMNS);
    downloadString(csv, `${filenameBase}.csv`, 'text/csv;charset=utf-8');
  };

  const handleExportXls = () => {
    const xml = rowsToSpreadsheetXml(rowsForExport(sortedRows), EXPORT_COLUMNS);
    downloadString(
      xml,
      `${filenameBase}.xls`,
      'application/vnd.ms-excel;charset=utf-8',
    );
  };

  const handleSavePreset = () => {
    const name = presetName.trim();
    if (!name) return;
    const next: TablePreset = {
      name,
      filters,
      savedAt: new Date().toISOString(),
    };
    const others = presets.filter((p) => p.name !== name);
    const updated = [...others, next].sort((a, b) =>
      a.name.localeCompare(b.name, 'ru'),
    );
    setPresets(updated);
    writePresets(updated);
    setPresetName('');
  };

  const handleLoadPreset = (name: string) => {
    if (!name) return;
    const preset = presets.find((p) => p.name === name);
    if (!preset) return;
    setSearchParams(writeFilters(preset.filters), { replace: true });
  };

  const handleDeletePreset = (name: string) => {
    const updated = presets.filter((p) => p.name !== name);
    setPresets(updated);
    writePresets(updated);
  };

  useEffect(() => {
    setMetricMin('');
    setMetricMax('');
  }, [filters.metric]);

  return (
    <div className="flex h-full flex-col gap-6 p-6 md:p-8">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Таблицы</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Гибкая таблица с агрегациями, сортировкой, фильтрацией и экспортом.
        </p>
      </header>

      <FiltersForm
        filters={filters}
        onChange={updateFilters}
        locations={sortedLocations}
        locationsLoading={locationsQuery.isLoading}
        onToggleLocation={toggleLocation}
        onToggleParameter={toggleParameter}
      />

      <PresetBar
        presets={presets}
        presetName={presetName}
        onNameChange={setPresetName}
        onSave={handleSavePreset}
        onLoad={handleLoadPreset}
        onDelete={handleDeletePreset}
      />

      <Card>
        <CardContent className="flex flex-col gap-4 p-6">
          <div className="flex flex-wrap items-end gap-3">
            <div className="grow min-w-[200px]">
              <Label className="mb-2 block text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Поиск
              </Label>
              <Input
                value={textFilter}
                onChange={(e) => setTextFilter(e.target.value)}
                placeholder="Период / локация / параметр"
              />
            </div>
            <div className="w-32">
              <Label className="mb-2 block text-xs font-medium uppercase tracking-wide text-muted-foreground">
                {filters.metric} ≥
              </Label>
              <Input
                type="number"
                value={metricMin}
                onChange={(e) => setMetricMin(e.target.value)}
              />
            </div>
            <div className="w-32">
              <Label className="mb-2 block text-xs font-medium uppercase tracking-wide text-muted-foreground">
                {filters.metric} ≤
              </Label>
              <Input
                type="number"
                value={metricMax}
                onChange={(e) => setMetricMax(e.target.value)}
              />
            </div>
            <div className="ml-auto flex flex-wrap gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={handleExportCsv}
                disabled={sortedRows.length === 0}
              >
                <Download className="mr-1 h-4 w-4" /> CSV
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={handleExportXls}
                disabled={sortedRows.length === 0}
              >
                <Download className="mr-1 h-4 w-4" /> Excel
              </Button>
            </div>
          </div>

          <StatsTable
            rows={sortedRows}
            sort={sort}
            onSort={toggleSort}
            metric={filters.metric}
            scales={scalesByParameter}
            queryEnabled={queryEnabled}
            loading={statsQuery.isLoading}
            error={statsQuery.error ?? null}
            onRetry={() => void statsQuery.refetch()}
          />
        </CardContent>
      </Card>
    </div>
  );
}

interface FiltersFormProps {
  filters: TableFilters;
  onChange: (patch: Partial<TableFilters>) => void;
  locations: Location[];
  locationsLoading: boolean;
  onToggleLocation: (id: number) => void;
  onToggleParameter: (p: string) => void;
}

function FiltersForm(props: FiltersFormProps) {
  const { filters, onChange, locations, locationsLoading } = props;
  return (
    <Card>
      <CardContent className="grid gap-6 p-6 md:grid-cols-2 lg:grid-cols-4">
        <FilterBlock label="Источник">
          <Select
            value={filters.source}
            onValueChange={(v) => onChange({ source: v as WeatherSource })}
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {SOURCES.map((s) => (
                <SelectItem key={s.value} value={s.value}>
                  {s.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </FilterBlock>

        <FilterBlock label="Период">
          <Select
            value={filters.period}
            onValueChange={(v) => onChange({ period: v as PeriodPreset })}
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {PERIOD_PRESETS.map((p) => (
                <SelectItem key={p.value} value={p.value}>
                  {p.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {filters.period === 'custom' && (
            <div className="mt-2 grid grid-cols-2 gap-2">
              <Input
                type="date"
                value={filters.customFrom}
                onChange={(e) => onChange({ customFrom: e.target.value })}
              />
              <Input
                type="date"
                value={filters.customTo}
                onChange={(e) => onChange({ customTo: e.target.value })}
              />
            </div>
          )}
        </FilterBlock>

        <FilterBlock label="Группировка">
          <Select
            value={filters.aggregation}
            onValueChange={(v) =>
              onChange({ aggregation: v as StatsAggregation })
            }
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {AGGREGATIONS.map((a) => (
                <SelectItem key={a.value} value={a.value}>
                  {a.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </FilterBlock>

        <FilterBlock label="Метрика для подсветки">
          <Select
            value={filters.metric}
            onValueChange={(v) => onChange({ metric: v as Metric })}
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {METRICS.map((m) => (
                <SelectItem key={m.value} value={m.value}>
                  {m.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </FilterBlock>

        <FilterBlock label="Локации" className="md:col-span-2 lg:col-span-4">
          {locationsLoading ? (
            <Skeleton className="h-10 w-full" />
          ) : locations.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              Локаций нет. Добавьте на странице «Локации».
            </p>
          ) : (
            <ChipGroup
              options={locations.map((l) => ({
                key: String(l.id),
                label: l.name,
                selected: filters.locationIds.includes(l.id),
                onToggle: () => props.onToggleLocation(l.id),
              }))}
            />
          )}
        </FilterBlock>

        <FilterBlock label="Параметры" className="md:col-span-2 lg:col-span-4">
          <ChipGroup
            options={WEATHER_PARAMETERS.map((p) => ({
              key: p,
              label: p,
              selected: filters.parameters.includes(p),
              onToggle: () => props.onToggleParameter(p),
            }))}
          />
        </FilterBlock>
      </CardContent>
    </Card>
  );
}

function FilterBlock(props: {
  label: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={props.className}>
      <Label className="mb-2 block text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {props.label}
      </Label>
      {props.children}
    </div>
  );
}

interface ChipOption {
  key: string;
  label: string;
  selected: boolean;
  onToggle: () => void;
}

function ChipGroup({ options }: { options: ChipOption[] }) {
  return (
    <div className="flex max-h-40 flex-wrap gap-2 overflow-auto">
      {options.map((opt) => (
        <button
          key={opt.key}
          type="button"
          onClick={opt.onToggle}
          className={`rounded-full border px-3 py-1 text-xs transition ${
            opt.selected
              ? 'border-primary bg-primary text-primary-foreground'
              : 'border-input bg-background text-foreground hover:bg-accent'
          }`}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}

interface PresetBarProps {
  presets: TablePreset[];
  presetName: string;
  onNameChange: (v: string) => void;
  onSave: () => void;
  onLoad: (name: string) => void;
  onDelete: (name: string) => void;
}

function PresetBar(props: PresetBarProps) {
  return (
    <Card>
      <CardContent className="flex flex-wrap items-end gap-3 p-6">
        <div className="grow min-w-[200px]">
          <Label className="mb-2 block text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Пресет — название
          </Label>
          <Input
            value={props.presetName}
            onChange={(e) => props.onNameChange(e.target.value)}
            placeholder="Напр. «Лето: температура»"
          />
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={props.onSave}
          disabled={!props.presetName.trim()}
        >
          <Save className="mr-1 h-4 w-4" /> Сохранить
        </Button>
        <div className="min-w-[220px]">
          <Label className="mb-2 block text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Загрузить пресет
          </Label>
          <Select
            value=""
            onValueChange={(v) => props.onLoad(v)}
            disabled={props.presets.length === 0}
          >
            <SelectTrigger>
              <SelectValue
                placeholder={
                  props.presets.length === 0 ? 'Нет пресетов' : 'Выберите…'
                }
              />
            </SelectTrigger>
            <SelectContent>
              {props.presets.map((p) => (
                <SelectItem key={p.name} value={p.name}>
                  {p.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        {props.presets.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {props.presets.map((p) => (
              <button
                key={p.name}
                type="button"
                onClick={() => props.onDelete(p.name)}
                className="inline-flex items-center gap-1 rounded-full border border-input bg-background px-3 py-1 text-xs text-muted-foreground hover:bg-accent"
                title={`Удалить пресет «${p.name}»`}
              >
                <Trash2 className="h-3 w-3" />
                {p.name}
              </button>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

interface StatsTableProps {
  rows: DisplayRow[];
  sort: SortState;
  onSort: (key: SortKey) => void;
  metric: Metric;
  scales: Map<string, { min: number; max: number }>;
  queryEnabled: boolean;
  loading: boolean;
  error: Error | null;
  onRetry: () => void;
}

function StatsTable(props: StatsTableProps) {
  if (!props.queryEnabled) {
    return (
      <div className="flex h-40 items-center justify-center text-sm text-muted-foreground">
        Выберите хотя бы одну локацию и один параметр.
      </div>
    );
  }
  if (props.loading) {
    return (
      <div className="flex h-40 items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }
  if (props.error) {
    return (
      <div className="flex h-40 flex-col items-center justify-center gap-3 text-center">
        <p className="text-sm text-destructive">
          {getErrorMessage(props.error)}
        </p>
        <Button variant="outline" size="sm" onClick={props.onRetry}>
          Повторить
        </Button>
      </div>
    );
  }
  if (props.rows.length === 0) {
    return (
      <div className="flex h-40 items-center justify-center text-sm text-muted-foreground">
        Нет данных по выбранным фильтрам.
      </div>
    );
  }

  return (
    <div className="overflow-auto">
      <Table>
        <TableHeader>
          <TableRow>
            <SortableHead
              label="Период"
              colKey="time"
              sort={props.sort}
              onSort={props.onSort}
            />
            <SortableHead
              label="Локация"
              colKey="location"
              sort={props.sort}
              onSort={props.onSort}
            />
            <SortableHead
              label="Параметр"
              colKey="parameter"
              sort={props.sort}
              onSort={props.onSort}
            />
            <SortableHead
              label="Min"
              colKey="min"
              sort={props.sort}
              onSort={props.onSort}
              numeric
            />
            <SortableHead
              label="Max"
              colKey="max"
              sort={props.sort}
              onSort={props.onSort}
              numeric
            />
            <SortableHead
              label="Mean"
              colKey="mean"
              sort={props.sort}
              onSort={props.onSort}
              numeric
            />
            <SortableHead
              label="Sum"
              colKey="sum"
              sort={props.sort}
              onSort={props.onSort}
              numeric
            />
            <SortableHead
              label="N"
              colKey="count"
              sort={props.sort}
              onSort={props.onSort}
              numeric
            />
          </TableRow>
        </TableHeader>
        <TableBody>
          {props.rows.map((row) => {
            const scale = props.scales.get(row.parameter);
            const highlightValue = row[props.metric];
            const bg = colorForCell(
              typeof highlightValue === 'number' ? highlightValue : null,
              scale,
            );
            const metricCellStyle = bg ? { backgroundColor: bg } : undefined;
            return (
              <TableRow key={row.key}>
                <TableCell className="whitespace-nowrap font-medium">
                  {row.bucket}
                </TableCell>
                <TableCell className="whitespace-nowrap">
                  {row.locationName}
                </TableCell>
                <TableCell className="whitespace-nowrap font-mono text-xs">
                  {row.parameter}
                </TableCell>
                <TableCell
                  className="text-right font-mono tabular-nums"
                  style={props.metric === 'min' ? metricCellStyle : undefined}
                >
                  {formatNumber(row.min)}
                </TableCell>
                <TableCell
                  className="text-right font-mono tabular-nums"
                  style={props.metric === 'max' ? metricCellStyle : undefined}
                >
                  {formatNumber(row.max)}
                </TableCell>
                <TableCell
                  className="text-right font-mono tabular-nums"
                  style={props.metric === 'mean' ? metricCellStyle : undefined}
                >
                  {formatNumber(row.mean)}
                </TableCell>
                <TableCell
                  className="text-right font-mono tabular-nums"
                  style={props.metric === 'sum' ? metricCellStyle : undefined}
                >
                  {formatNumber(row.sum)}
                </TableCell>
                <TableCell
                  className="text-right font-mono tabular-nums"
                  style={props.metric === 'count' ? metricCellStyle : undefined}
                >
                  {row.count}
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}

interface SortableHeadProps {
  label: string;
  colKey: SortKey;
  sort: SortState;
  onSort: (key: SortKey) => void;
  numeric?: boolean;
}

function SortableHead(props: SortableHeadProps) {
  const active = props.sort.key === props.colKey;
  const arrow = active ? (props.sort.dir === 'asc' ? '↑' : '↓') : '';
  return (
    <TableHead className={props.numeric ? 'text-right' : ''}>
      <button
        type="button"
        onClick={() => props.onSort(props.colKey)}
        className="inline-flex items-center gap-1 font-medium text-muted-foreground hover:text-foreground"
      >
        {props.label}
        <span className="text-xs">{arrow}</span>
      </button>
    </TableHead>
  );
}

export default TablesPage;
