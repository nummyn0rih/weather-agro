import { useQuery } from '@tanstack/react-query';
import axios from 'axios';
import { Download, Image as ImageIcon, Loader2 } from 'lucide-react';
import type Plotly from 'plotly.js';
import { type CSSProperties, useCallback, useMemo, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import { PlotlyChart } from '@/components/charts/PlotlyChart';
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
  type CorrelationMatrix,
  getCorrelations,
} from '@/lib/analytics-api';
import {
  type ChartType,
  makeLocationLookup,
  pivotCompareLocations,
  pivotCumulative,
  pivotOverlayYears,
  pivotTimeseries,
} from '@/lib/chart-data';
import {
  downloadString,
  exportContainerPng,
  exportContainerSvg,
  rowsToCsv,
} from '@/lib/chart-export';
import { listLocations, type Location } from '@/lib/locations-api';
import {
  type CumulativeParameter,
  type CumulativePoint,
  type HeatmapCell,
  type HeatmapXAxis,
  type WeatherDailyPoint,
  type WeatherSource,
  WEATHER_PARAMETERS,
  downloadWeatherExport,
  getWeatherCumulative,
  getWeatherDaily,
  getWeatherHeatmap,
} from '@/lib/weather-api';

type PeriodPreset = '7d' | '30d' | '90d' | '365d' | 'ytd' | 'custom';

const CHART_TYPES: { value: ChartType; label: string }[] = [
  { value: 'timeseries', label: 'Временной ряд' },
  { value: 'compare_locations', label: 'Сравнение локаций' },
  { value: 'overlay_years', label: 'Overlay по годам' },
  { value: 'cumulative', label: 'Накопительный' },
  { value: 'heatmap', label: 'Heatmap' },
  { value: 'correlations', label: 'Корреляции' },
];

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

const CUMULATIVE_PARAMETERS: {
  value: CumulativeParameter;
  label: string;
}[] = [
  { value: 'precipitation', label: 'Осадки' },
  { value: 'et0', label: 'ET₀' },
  { value: 'sunshine_hours', label: 'Часы солнца' },
  { value: 'gdd', label: 'GDD' },
];

const HEATMAP_AXES: { value: HeatmapXAxis; label: string }[] = [
  { value: 'month', label: 'Месяц' },
  { value: 'week', label: 'Неделя' },
  { value: 'doy', label: 'День года' },
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

function resolvePeriod(preset: PeriodPreset, customFrom: string, customTo: string): {
  date_from: string;
  date_to: string;
} {
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
  return value.split(',').map((v) => v.trim()).filter(Boolean);
}

function getErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data as { detail?: string } | undefined;
    if (typeof data?.detail === 'string') return data.detail;
    return error.message;
  }
  return error instanceof Error ? error.message : 'Неизвестная ошибка';
}

interface ChartFilters {
  chart: ChartType;
  locationIds: number[];
  parameters: string[];
  period: PeriodPreset;
  customFrom: string;
  customTo: string;
  source: WeatherSource;
  compareYears: number[];
  axis: HeatmapXAxis;
  cumulativeParameter: CumulativeParameter;
  baseTemperature: string;
}

function readFilters(params: URLSearchParams): ChartFilters {
  const chart = (params.get('chart') ?? 'timeseries') as ChartType;
  const period = (params.get('period') ?? '30d') as PeriodPreset;
  const today = todayIso();
  return {
    chart,
    locationIds: parseCsvNumbers(params.get('locations')),
    parameters: parseCsvStrings(params.get('parameters')),
    period,
    customFrom: params.get('from') ?? addDaysIso(today, -29),
    customTo: params.get('to') ?? today,
    source: (params.get('source') ?? 'average') as WeatherSource,
    compareYears: parseCsvNumbers(params.get('years')),
    axis: (params.get('axis') ?? 'month') as HeatmapXAxis,
    cumulativeParameter: (params.get('cum') ?? 'precipitation') as CumulativeParameter,
    baseTemperature: params.get('base') ?? '',
  };
}

function writeFilters(filters: ChartFilters): URLSearchParams {
  const next = new URLSearchParams();
  next.set('chart', filters.chart);
  next.set('period', filters.period);
  next.set('source', filters.source);
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
  if (filters.chart === 'overlay_years' && filters.compareYears.length > 0) {
    next.set('years', filters.compareYears.join(','));
  }
  if (filters.chart === 'heatmap') {
    next.set('axis', filters.axis);
  }
  if (filters.chart === 'cumulative') {
    next.set('cum', filters.cumulativeParameter);
    if (filters.baseTemperature) next.set('base', filters.baseTemperature);
  }
  return next;
}

export function ChartsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const filters = useMemo(() => readFilters(searchParams), [searchParams]);

  const updateFilters = useCallback(
    (patch: Partial<ChartFilters>) => {
      const next = { ...filters, ...patch };
      setSearchParams(writeFilters(next), { replace: true });
    },
    [filters, setSearchParams],
  );

  const locationsQuery = useQuery<Location[], Error>({
    queryKey: ['locations'],
    queryFn: () => listLocations(),
  });

  return (
    <div className="flex h-full flex-col gap-6 p-6 md:p-8">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Графики</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Интерактивные графики, тепловые карты и матрица корреляций.
        </p>
      </header>

      <ChartFiltersForm
        filters={filters}
        onChange={updateFilters}
        locations={locationsQuery.data ?? []}
        locationsLoading={locationsQuery.isLoading}
      />

      <ChartArea
        filters={filters}
        locations={locationsQuery.data ?? []}
        locationsReady={!locationsQuery.isLoading && !locationsQuery.isError}
      />
    </div>
  );
}

function ChartFiltersForm(props: {
  filters: ChartFilters;
  onChange: (patch: Partial<ChartFilters>) => void;
  locations: Location[];
  locationsLoading: boolean;
}) {
  const { filters, onChange, locations, locationsLoading } = props;

  const sortedLocations = useMemo(
    () =>
      [...locations].sort((a, b) => a.name.localeCompare(b.name, 'ru')),
    [locations],
  );

  const toggleLocation = (id: number) => {
    const present = filters.locationIds.includes(id);
    onChange({
      locationIds: present
        ? filters.locationIds.filter((v) => v !== id)
        : [...filters.locationIds, id],
    });
  };

  const toggleParameter = (p: string) => {
    const present = filters.parameters.includes(p);
    onChange({
      parameters: present
        ? filters.parameters.filter((v) => v !== p)
        : [...filters.parameters, p],
    });
  };

  return (
    <Card>
      <CardContent className="grid gap-6 p-6 md:grid-cols-2 lg:grid-cols-3">
        <FilterBlock label="Тип графика">
          <Select
            value={filters.chart}
            onValueChange={(v) => onChange({ chart: v as ChartType })}
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {CHART_TYPES.map((t) => (
                <SelectItem key={t.value} value={t.value}>
                  {t.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </FilterBlock>

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

        <FilterBlock label="Локации" className="md:col-span-2 lg:col-span-3">
          {locationsLoading ? (
            <Skeleton className="h-10 w-full" />
          ) : sortedLocations.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              Локаций нет. Добавьте на странице «Локации».
            </p>
          ) : (
            <ChipGroup
              options={sortedLocations.map((l) => ({
                key: String(l.id),
                label: l.name,
                selected: filters.locationIds.includes(l.id),
                onToggle: () => toggleLocation(l.id),
              }))}
            />
          )}
        </FilterBlock>

        {filters.chart !== 'cumulative' && (
          <FilterBlock label="Параметры" className="md:col-span-2 lg:col-span-3">
            <ChipGroup
              options={WEATHER_PARAMETERS.map((p) => ({
                key: p,
                label: p,
                selected: filters.parameters.includes(p),
                onToggle: () => toggleParameter(p),
              }))}
            />
          </FilterBlock>
        )}

        {filters.chart === 'overlay_years' && (
          <FilterBlock label="Годы для overlay (через запятую)">
            <Input
              placeholder="2022,2023,2024"
              value={filters.compareYears.join(',')}
              onChange={(e) =>
                onChange({ compareYears: parseCsvNumbers(e.target.value) })
              }
            />
          </FilterBlock>
        )}

        {filters.chart === 'heatmap' && (
          <FilterBlock label="Ось X (heatmap)">
            <Select
              value={filters.axis}
              onValueChange={(v) => onChange({ axis: v as HeatmapXAxis })}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {HEATMAP_AXES.map((a) => (
                  <SelectItem key={a.value} value={a.value}>
                    {a.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </FilterBlock>
        )}

        {filters.chart === 'cumulative' && (
          <>
            <FilterBlock label="Параметр (накопительный)">
              <Select
                value={filters.cumulativeParameter}
                onValueChange={(v) =>
                  onChange({ cumulativeParameter: v as CumulativeParameter })
                }
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {CUMULATIVE_PARAMETERS.map((c) => (
                    <SelectItem key={c.value} value={c.value}>
                      {c.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </FilterBlock>
            {filters.cumulativeParameter === 'gdd' && (
              <FilterBlock label="Base T° (для GDD)">
                <Input
                  type="number"
                  step="0.1"
                  placeholder="10"
                  value={filters.baseTemperature}
                  onChange={(e) =>
                    onChange({ baseTemperature: e.target.value })
                  }
                />
              </FilterBlock>
            )}
          </>
        )}
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

function ChartArea(props: {
  filters: ChartFilters;
  locations: Location[];
  locationsReady: boolean;
}) {
  const { filters, locations, locationsReady } = props;

  if (!locationsReady) {
    return <Skeleton className="h-96 w-full" />;
  }

  switch (filters.chart) {
    case 'timeseries':
    case 'compare_locations':
    case 'overlay_years':
      return <DailyChart filters={filters} locations={locations} />;
    case 'cumulative':
      return <CumulativeChart filters={filters} locations={locations} />;
    case 'heatmap':
      return <HeatmapChart filters={filters} />;
    case 'correlations':
      return <CorrelationsChart filters={filters} />;
  }
}

function ChartCard(props: {
  children?: React.ReactNode;
  toolbar?: React.ReactNode;
  empty?: boolean;
  emptyMessage?: string;
  loading?: boolean;
  error?: Error | null;
  onRetry?: () => void;
  containerRef?: React.RefObject<HTMLDivElement | null>;
}) {
  return (
    <Card>
      <CardContent className="flex flex-col gap-4 p-6">
        {props.toolbar && (
          <div className="flex flex-wrap items-center justify-end gap-2">
            {props.toolbar}
          </div>
        )}
        <div
          ref={props.containerRef as React.RefObject<HTMLDivElement>}
          className="h-[480px] w-full"
          style={{ minHeight: 320 }}
        >
          {props.loading ? (
            <div className="flex h-full items-center justify-center">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : props.error ? (
            <ErrorState error={props.error} onRetry={props.onRetry} />
          ) : props.empty ? (
            <EmptyState message={props.emptyMessage} />
          ) : (
            props.children
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function EmptyState({ message }: { message?: string }) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-2 text-center">
      <p className="text-sm text-muted-foreground">
        {message ?? 'Нет данных по выбранным фильтрам.'}
      </p>
    </div>
  );
}

function ErrorState({
  error,
  onRetry,
}: {
  error: Error;
  onRetry?: () => void;
}) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 text-center">
      <p className="text-sm text-destructive">{getErrorMessage(error)}</p>
      {onRetry && (
        <Button variant="outline" size="sm" onClick={onRetry}>
          Повторить
        </Button>
      )}
    </div>
  );
}

interface ExportToolbarProps {
  containerRef: React.RefObject<HTMLDivElement | null>;
  filenameBase: string;
  csvRows: Record<string, unknown>[];
  csvColumns: string[];
  disabled?: boolean;
  onServerCsv?: () => void;
}

function ExportToolbar(props: ExportToolbarProps) {
  const handlePng = () => {
    void (async () => {
      try {
        await exportContainerPng(
          props.containerRef.current,
          `${props.filenameBase}.png`,
        );
      } catch (err) {
        console.error(err);
      }
    })();
  };

  const handleSvg = () => {
    try {
      exportContainerSvg(
        props.containerRef.current,
        `${props.filenameBase}.svg`,
      );
    } catch (err) {
      console.error(err);
    }
  };

  const handleCsv = () => {
    if (props.onServerCsv) {
      props.onServerCsv();
      return;
    }
    const csv = rowsToCsv(props.csvRows, props.csvColumns);
    downloadString(csv, `${props.filenameBase}.csv`, 'text/csv;charset=utf-8');
  };

  return (
    <>
      <Button
        variant="outline"
        size="sm"
        onClick={handlePng}
        disabled={props.disabled}
      >
        <ImageIcon className="mr-1 h-4 w-4" /> PNG
      </Button>
      <Button
        variant="outline"
        size="sm"
        onClick={handleSvg}
        disabled={props.disabled}
      >
        <ImageIcon className="mr-1 h-4 w-4" /> SVG
      </Button>
      <Button
        variant="outline"
        size="sm"
        onClick={handleCsv}
        disabled={props.disabled}
      >
        <Download className="mr-1 h-4 w-4" /> CSV
      </Button>
    </>
  );
}

function DailyChart(props: { filters: ChartFilters; locations: Location[] }) {
  const { filters, locations } = props;
  const containerRef = useRef<HTMLDivElement | null>(null);
  const period = resolvePeriod(filters.period, filters.customFrom, filters.customTo);
  const isOverlay = filters.chart === 'overlay_years';

  const queryEnabled =
    filters.locationIds.length > 0 &&
    filters.parameters.length > 0 &&
    (!isOverlay || filters.compareYears.length > 0);

  const query = useQuery<WeatherDailyPoint[], Error>({
    queryKey: [
      'weather-daily-chart',
      filters.chart,
      filters.locationIds,
      filters.parameters,
      period,
      filters.source,
      filters.compareYears,
    ],
    queryFn: () =>
      getWeatherDaily({
        location_ids: filters.locationIds,
        parameters: filters.parameters,
        date_from: period.date_from,
        date_to: period.date_to,
        source: filters.source,
        ...(isOverlay ? { compare_years: filters.compareYears } : {}),
      }),
    enabled: queryEnabled,
  });

  const lookup = useMemo(() => makeLocationLookup(locations), [locations]);

  const { data, series } = useMemo(() => {
    const rows = query.data ?? [];
    if (filters.chart === 'compare_locations') {
      const param = filters.parameters[0] ?? '';
      return pivotCompareLocations(rows, param, lookup);
    }
    if (filters.chart === 'overlay_years') {
      const param = filters.parameters[0] ?? '';
      return pivotOverlayYears(rows, param);
    }
    return pivotTimeseries(rows, filters.parameters, lookup);
  }, [query.data, filters.chart, filters.parameters, lookup]);

  const handleServerCsv = useCallback(() => {
    void (async () => {
      try {
        const blob = await downloadWeatherExport({
          location_ids: filters.locationIds,
          parameters: filters.parameters,
          date_from: period.date_from,
          date_to: period.date_to,
          source: filters.source,
          format: 'csv',
        });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `weather_${period.date_from}_${period.date_to}.csv`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
      } catch (err) {
        console.error(err);
      }
    })();
  }, [filters, period]);

  if (!queryEnabled) {
    return (
      <ChartCard empty emptyMessage="Выберите локации и параметры." />
    );
  }

  const csvColumns = ['time', ...series.map((s) => s.key)];
  const filenameBase = `chart_${filters.chart}_${period.date_from}_${period.date_to}`;

  const toolbar = (
    <ExportToolbar
      containerRef={containerRef}
      filenameBase={filenameBase}
      csvRows={data}
      csvColumns={csvColumns}
      disabled={query.isLoading || !!query.error || data.length === 0}
      onServerCsv={isOverlay ? undefined : handleServerCsv}
    />
  );

  return (
    <ChartCard
      toolbar={toolbar}
      loading={query.isLoading}
      error={query.error ?? null}
      onRetry={() => void query.refetch()}
      empty={!query.isLoading && data.length === 0}
      containerRef={containerRef}
    >
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="currentColor" opacity={0.1} />
          <XAxis dataKey="time" tick={{ fontSize: 12 }} />
          <YAxis tick={{ fontSize: 12 }} />
          <Tooltip />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          {series.map((s) => (
            <Line
              key={s.key}
              type="monotone"
              dataKey={s.key}
              stroke={s.color}
              dot={false}
              strokeWidth={2}
              isAnimationActive={false}
              connectNulls
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}

function CumulativeChart(props: {
  filters: ChartFilters;
  locations: Location[];
}) {
  const { filters, locations } = props;
  const containerRef = useRef<HTMLDivElement | null>(null);
  const period = resolvePeriod(filters.period, filters.customFrom, filters.customTo);

  const baseTempNumber = filters.baseTemperature
    ? Number(filters.baseTemperature)
    : undefined;
  const baseTempValid =
    filters.cumulativeParameter !== 'gdd' ||
    (baseTempNumber !== undefined && Number.isFinite(baseTempNumber));

  const queryEnabled = filters.locationIds.length > 0 && baseTempValid;

  const query = useQuery<CumulativePoint[], Error>({
    queryKey: [
      'weather-cumulative',
      filters.locationIds,
      filters.cumulativeParameter,
      period,
      filters.source,
      baseTempNumber,
    ],
    queryFn: () =>
      getWeatherCumulative({
        location_ids: filters.locationIds,
        parameter: filters.cumulativeParameter,
        date_from: period.date_from,
        date_to: period.date_to,
        source: filters.source,
        ...(baseTempNumber !== undefined && Number.isFinite(baseTempNumber)
          ? { base_temperature: baseTempNumber }
          : {}),
      }),
    enabled: queryEnabled,
  });

  const lookup = useMemo(() => makeLocationLookup(locations), [locations]);
  const { data, series } = useMemo(
    () => pivotCumulative(query.data ?? [], lookup),
    [query.data, lookup],
  );

  if (!queryEnabled) {
    return (
      <ChartCard
        empty
        emptyMessage={
          filters.cumulativeParameter === 'gdd'
            ? 'Укажите локации и базовую температуру для GDD.'
            : 'Выберите локации.'
        }
      />
    );
  }

  const csvColumns = ['time', ...series.map((s) => s.key)];
  const filenameBase = `cumulative_${filters.cumulativeParameter}_${period.date_from}_${period.date_to}`;

  return (
    <ChartCard
      toolbar={
        <ExportToolbar
          containerRef={containerRef}
          filenameBase={filenameBase}
          csvRows={data}
          csvColumns={csvColumns}
          disabled={query.isLoading || !!query.error || data.length === 0}
        />
      }
      loading={query.isLoading}
      error={query.error ?? null}
      onRetry={() => void query.refetch()}
      empty={!query.isLoading && data.length === 0}
      containerRef={containerRef}
    >
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="currentColor" opacity={0.1} />
          <XAxis dataKey="time" tick={{ fontSize: 12 }} />
          <YAxis tick={{ fontSize: 12 }} />
          <Tooltip />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          {series.map((s) => (
            <Line
              key={s.key}
              type="monotone"
              dataKey={s.key}
              stroke={s.color}
              dot={false}
              strokeWidth={2}
              isAnimationActive={false}
              connectNulls
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}

function HeatmapChart({ filters }: { filters: ChartFilters }) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const period = resolvePeriod(filters.period, filters.customFrom, filters.customTo);
  const locationId = filters.locationIds[0];
  const parameter = filters.parameters[0];

  const queryEnabled = locationId !== undefined && parameter !== undefined;

  const query = useQuery<HeatmapCell[], Error>({
    queryKey: [
      'weather-heatmap',
      locationId,
      parameter,
      period,
      filters.source,
      filters.axis,
    ],
    queryFn: () =>
      getWeatherHeatmap({
        location_id: locationId,
        parameter: parameter,
        date_from: period.date_from,
        date_to: period.date_to,
        source: filters.source,
        axis: filters.axis,
      }),
    enabled: queryEnabled,
  });

  const matrix = useMemo(() => buildHeatmapMatrix(query.data ?? []), [query.data]);
  const filenameBase = `heatmap_${parameter ?? 'param'}_${filters.axis}_${period.date_from}_${period.date_to}`;

  if (!queryEnabled) {
    return (
      <ChartCard
        empty
        emptyMessage="Heatmap: выберите одну локацию и один параметр."
      />
    );
  }

  const csvRows = matrix.years.flatMap((year, i) =>
    matrix.xs.map((x, j) => ({
      year,
      x,
      value: matrix.z[i]?.[j] ?? null,
    })),
  );

  return (
    <ChartCard
      toolbar={
        <ExportToolbar
          containerRef={containerRef}
          filenameBase={filenameBase}
          csvRows={csvRows}
          csvColumns={['year', 'x', 'value']}
          disabled={
            query.isLoading || !!query.error || matrix.years.length === 0
          }
        />
      }
      loading={query.isLoading}
      error={query.error ?? null}
      onRetry={() => void query.refetch()}
      empty={!query.isLoading && matrix.years.length === 0}
      containerRef={containerRef}
    >
      <PlotlyChart
        data={[
          {
            type: 'heatmap',
            x: matrix.xs,
            y: matrix.years,
            z: matrix.z,
            colorscale: 'Viridis',
            hoverongaps: false,
          },
        ]}
        layout={plotlyLayout({
          xaxisTitle: filters.axis,
          yaxisTitle: 'год',
        })}
        config={plotlyConfig()}
        useResizeHandler
        style={fillStyle}
      />
    </ChartCard>
  );
}

function CorrelationsChart({ filters }: { filters: ChartFilters }) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const period = resolvePeriod(filters.period, filters.customFrom, filters.customTo);
  const locationId = filters.locationIds[0];
  const queryEnabled = locationId !== undefined && filters.parameters.length >= 2;

  const query = useQuery<CorrelationMatrix, Error>({
    queryKey: [
      'analytics-correlations',
      locationId,
      filters.parameters,
      period,
      filters.source,
    ],
    queryFn: () =>
      getCorrelations({
        location_id: locationId,
        parameters: filters.parameters,
        date_from: period.date_from,
        date_to: period.date_to,
        source: filters.source,
      }),
    enabled: queryEnabled,
  });

  const filenameBase = `correlations_${period.date_from}_${period.date_to}`;

  if (!queryEnabled) {
    return (
      <ChartCard
        empty
        emptyMessage="Корреляции: выберите одну локацию и минимум 2 параметра."
      />
    );
  }

  const matrix = query.data;
  const csvRows = matrix
    ? matrix.parameters.flatMap((rowParam, i) =>
        matrix.parameters.map((colParam, j) => ({
          row: rowParam,
          col: colParam,
          r: matrix.matrix[i]?.[j] ?? null,
          n: matrix.counts[i]?.[j] ?? 0,
        })),
      )
    : [];

  return (
    <ChartCard
      toolbar={
        <ExportToolbar
          containerRef={containerRef}
          filenameBase={filenameBase}
          csvRows={csvRows}
          csvColumns={['row', 'col', 'r', 'n']}
          disabled={query.isLoading || !!query.error || !matrix}
        />
      }
      loading={query.isLoading}
      error={query.error ?? null}
      onRetry={() => void query.refetch()}
      empty={!query.isLoading && !matrix}
      containerRef={containerRef}
    >
      {matrix && (
        <PlotlyChart
          data={[
            {
              type: 'heatmap',
              x: matrix.parameters,
              y: matrix.parameters,
              z: matrix.matrix,
              zmin: -1,
              zmax: 1,
              colorscale: 'RdBu',
              reversescale: true,
              hoverongaps: false,
            },
          ]}
          layout={plotlyLayout({
            xaxisTitle: '',
            yaxisTitle: '',
          })}
          config={plotlyConfig()}
          useResizeHandler
          style={fillStyle}
        />
      )}
    </ChartCard>
  );
}

const fillStyle: CSSProperties = { width: '100%', height: '100%' };

function plotlyLayout(opts: { xaxisTitle: string; yaxisTitle: string }) {
  return {
    autosize: true,
    margin: { l: 60, r: 30, t: 20, b: 50 },
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    xaxis: { title: { text: opts.xaxisTitle } },
    yaxis: { title: { text: opts.yaxisTitle } },
    font: { family: 'Inter, sans-serif', size: 12 },
  };
}

function plotlyConfig(): Partial<Plotly.Config> {
  return {
    displaylogo: false,
    responsive: true,
    modeBarButtonsToRemove: ['lasso2d', 'select2d', 'autoScale2d'],
  };
}

function buildHeatmapMatrix(cells: HeatmapCell[]): {
  years: number[];
  xs: number[];
  z: (number | null)[][];
} {
  const yearSet = new Set<number>();
  const xSet = new Set<number>();
  for (const c of cells) {
    yearSet.add(c.year);
    xSet.add(c.x);
  }
  const years = [...yearSet].sort((a, b) => a - b);
  const xs = [...xSet].sort((a, b) => a - b);
  const yearIdx = new Map(years.map((y, i) => [y, i]));
  const xIdx = new Map(xs.map((x, i) => [x, i]));
  const z: (number | null)[][] = years.map(() => xs.map(() => null));
  for (const c of cells) {
    const yi = yearIdx.get(c.year);
    const xi = xIdx.get(c.x);
    if (yi === undefined || xi === undefined) continue;
    const row = z[yi];
    if (!row) continue;
    row[xi] = c.value;
  }
  return { years, xs, z };
}

export default ChartsPage;
