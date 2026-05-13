import { useQuery } from '@tanstack/react-query';
import axios from 'axios';
import { Loader2 } from 'lucide-react';
import type Plotly from 'plotly.js';
import { type CSSProperties, useMemo, useState } from 'react';
import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Scatter,
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
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  type AnomalyRow,
  type ClimateNormalRow,
  type CorrelationMatrix,
  type NormalPeriod,
  getAnomalies,
  getClimateNormals,
  getCorrelations,
} from '@/lib/analytics-api';
import { cn } from '@/lib/utils';
import { listLocations, type Location } from '@/lib/locations-api';
import {
  type WeatherSource,
  type WeatherStatsRow,
  WEATHER_PARAMETERS,
  getWeatherStats,
} from '@/lib/weather-api';

type TabId = 'stats' | 'anomalies' | 'correlations' | 'normals';
type PeriodPreset = '30d' | '90d' | '365d' | 'ytd' | 'custom';

interface BaseFilters {
  locationId: number | null;
  period: PeriodPreset;
  customFrom: string;
  customTo: string;
  source: WeatherSource;
  parameter: string;
  parameters: string[];
  normalPeriod: NormalPeriod;
}

const TABS: { id: TabId; label: string }[] = [
  { id: 'stats', label: 'Статистика' },
  { id: 'anomalies', label: 'Аномалии' },
  { id: 'correlations', label: 'Корреляции' },
  { id: 'normals', label: 'Climate normals' },
];

const SOURCES: { value: WeatherSource; label: string }[] = [
  { value: 'average', label: 'Среднее по источникам' },
  { value: 'open_meteo', label: 'Open-Meteo' },
  { value: 'nasa_power', label: 'NASA POWER' },
  { value: 'openweathermap', label: 'OpenWeatherMap' },
];

const PERIOD_PRESETS: { value: PeriodPreset; label: string }[] = [
  { value: '30d', label: '30 дней' },
  { value: '90d', label: '90 дней' },
  { value: '365d', label: 'Год' },
  { value: 'ytd', label: 'С начала года' },
  { value: 'custom', label: 'Произвольный' },
];

const NORMAL_PERIODS: { value: NormalPeriod; label: string }[] = [
  { value: 'month', label: 'Месяц' },
  { value: 'week', label: 'Неделя ISO' },
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
  return `${new Date().getUTCFullYear()}-01-01`;
}

function resolvePeriod(
  preset: PeriodPreset,
  from: string,
  to: string,
): { date_from: string; date_to: string } {
  const today = todayIso();
  switch (preset) {
    case '30d':
      return { date_from: addDaysIso(today, -29), date_to: today };
    case '90d':
      return { date_from: addDaysIso(today, -89), date_to: today };
    case '365d':
      return { date_from: addDaysIso(today, -364), date_to: today };
    case 'ytd':
      return { date_from: startOfYearIso(), date_to: today };
    case 'custom':
      return { date_from: from, date_to: to };
  }
}

function getErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data as { detail?: string } | undefined;
    if (typeof data?.detail === 'string') return data.detail;
    return error.message;
  }
  return error instanceof Error ? error.message : 'Неизвестная ошибка';
}

function formatNumber(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return '—';
  }
  return value.toFixed(digits);
}

const MONTH_LABELS = [
  'Янв',
  'Фев',
  'Мар',
  'Апр',
  'Май',
  'Июн',
  'Июл',
  'Авг',
  'Сен',
  'Окт',
  'Ноя',
  'Дек',
];

function bucketLabel(period: NormalPeriod, bucket: number): string {
  if (period === 'month') return MONTH_LABELS[bucket - 1] ?? String(bucket);
  if (period === 'week') return `W${bucket}`;
  return `D${bucket}`;
}

export function AnalyticsPage() {
  const [tab, setTab] = useState<TabId>('stats');
  const today = todayIso();
  const [filters, setFilters] = useState<BaseFilters>({
    locationId: null,
    period: '90d',
    customFrom: addDaysIso(today, -89),
    customTo: today,
    source: 'average',
    parameter: 'temp_avg',
    parameters: ['temp_avg', 'precipitation', 'humidity_avg'],
    normalPeriod: 'month',
  });

  const locationsQuery = useQuery<Location[], Error>({
    queryKey: ['locations'],
    queryFn: () => listLocations(),
  });

  const update = (patch: Partial<BaseFilters>) =>
    setFilters((prev) => ({ ...prev, ...patch }));

  const locations = useMemo(
    () =>
      [...(locationsQuery.data ?? [])].sort((a, b) =>
        a.name.localeCompare(b.name, 'ru'),
      ),
    [locationsQuery.data],
  );

  return (
    <div className="surface-apple flex h-full flex-col gap-8 p-6 md:gap-10 md:p-10">
      <header>
        <h1 className="text-display-sm font-semibold tracking-apple-tight text-apple-text">
          Аналитика
        </h1>
        <p className="mt-2 text-base text-apple-text-secondary">
          Сводная статистика, аномалии, корреляции и climate normals.
        </p>
      </header>

      <FiltersPanel
        tab={tab}
        filters={filters}
        onChange={update}
        locations={locations}
        locationsLoading={locationsQuery.isLoading}
      />

      <TabsBar tab={tab} onChange={setTab} />

      <TabContent
        tab={tab}
        filters={filters}
        locations={locations}
        locationsReady={!locationsQuery.isLoading && !locationsQuery.isError}
      />
    </div>
  );
}

function TabsBar({
  tab,
  onChange,
}: {
  tab: TabId;
  onChange: (id: TabId) => void;
}) {
  return (
    <div
      className="flex flex-wrap gap-1 border-b border-apple-separator"
      role="tablist"
      aria-label="Аналитика — разделы"
    >
      {TABS.map((t) => (
        <button
          key={t.id}
          type="button"
          role="tab"
          aria-selected={tab === t.id}
          onClick={() => onChange(t.id)}
          className={cn(
            '-mb-px border-b-2 px-4 py-2.5 text-sm transition-all duration-200 ease-apple focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-apple-blue focus-visible:ring-offset-2 focus-visible:ring-offset-apple-bg',
            tab === t.id
              ? 'border-apple-blue font-medium text-apple-blue'
              : 'border-transparent text-apple-text-secondary hover:text-apple-text',
          )}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}

function FiltersPanel(props: {
  tab: TabId;
  filters: BaseFilters;
  onChange: (patch: Partial<BaseFilters>) => void;
  locations: Location[];
  locationsLoading: boolean;
}) {
  const { tab, filters, onChange, locations, locationsLoading } = props;

  const showSingleParam = tab === 'anomalies' || tab === 'normals';
  const showMultiParam = tab === 'stats' || tab === 'correlations';
  const showNormalPeriod = tab === 'anomalies' || tab === 'normals';

  return (
    <Card className="rounded-apple-lg border-0 bg-apple-surface shadow-apple-md">
      <CardContent className="grid gap-6 p-6 md:grid-cols-2 lg:grid-cols-3 md:p-8">
        <FilterBlock label="Локация">
          {locationsLoading ? (
            <Skeleton className="h-10 w-full" />
          ) : locations.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              Локаций нет. Добавьте на странице «Локации».
            </p>
          ) : (
            <Select
              value={filters.locationId ? String(filters.locationId) : ''}
              onValueChange={(v) => onChange({ locationId: Number(v) })}
            >
              <SelectTrigger>
                <SelectValue placeholder="Выберите локацию" />
              </SelectTrigger>
              <SelectContent>
                {locations.map((l) => (
                  <SelectItem key={l.id} value={String(l.id)}>
                    {l.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
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

        {showSingleParam && (
          <FilterBlock label="Параметр">
            <Select
              value={filters.parameter}
              onValueChange={(v) => onChange({ parameter: v })}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {WEATHER_PARAMETERS.map((p) => (
                  <SelectItem key={p} value={p}>
                    {p}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </FilterBlock>
        )}

        {showNormalPeriod && (
          <FilterBlock label="Бакет норм">
            <Select
              value={filters.normalPeriod}
              onValueChange={(v) =>
                onChange({ normalPeriod: v as NormalPeriod })
              }
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {NORMAL_PERIODS.map((p) => (
                  <SelectItem key={p.value} value={p.value}>
                    {p.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </FilterBlock>
        )}

        {showMultiParam && (
          <FilterBlock
            label="Параметры"
            className="md:col-span-2 lg:col-span-3"
          >
            <ChipGroup
              options={WEATHER_PARAMETERS.map((p) => ({
                key: p,
                label: p,
                selected: filters.parameters.includes(p),
                onToggle: () => {
                  const present = filters.parameters.includes(p);
                  onChange({
                    parameters: present
                      ? filters.parameters.filter((v) => v !== p)
                      : [...filters.parameters, p],
                  });
                },
              }))}
            />
          </FilterBlock>
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
      <Label className="mb-2 block text-xs font-medium uppercase tracking-wide text-apple-text-tertiary">
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
          className={cn(
            'rounded-apple-full border px-3.5 py-1.5 text-xs font-medium transition-all duration-200 ease-apple focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-apple-blue focus-visible:ring-offset-2 focus-visible:ring-offset-apple-bg',
            opt.selected
              ? 'border-transparent bg-apple-blue text-white shadow-apple-sm'
              : 'border-apple-separator bg-apple-surface text-apple-text-secondary hover:bg-apple-blue-pastel hover:text-apple-blue',
          )}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}

function TabContent(props: {
  tab: TabId;
  filters: BaseFilters;
  locations: Location[];
  locationsReady: boolean;
}) {
  if (!props.locationsReady) {
    return <Skeleton className="h-96 w-full rounded-apple-lg bg-apple-bg" />;
  }
  switch (props.tab) {
    case 'stats':
      return <StatsTab filters={props.filters} />;
    case 'anomalies':
      return <AnomaliesTab filters={props.filters} />;
    case 'correlations':
      return <CorrelationsTab filters={props.filters} />;
    case 'normals':
      return <NormalsTab filters={props.filters} />;
  }
}

function PanelCard(props: {
  children?: React.ReactNode;
  empty?: boolean;
  emptyMessage?: string;
  loading?: boolean;
  error?: Error | null;
  onRetry?: () => void;
  height?: number;
}) {
  return (
    <Card className="rounded-apple-lg border-0 bg-apple-surface shadow-apple-md">
      <CardContent className="flex flex-col gap-4 p-6 md:p-8">
        <div
          className="w-full"
          style={{ minHeight: props.height ?? 320 }}
        >
          {props.loading ? (
            <div className="flex h-80 items-center justify-center">
              <Loader2 className="h-6 w-6 animate-spin text-apple-text-tertiary" />
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
    <div className="flex h-80 flex-col items-center justify-center gap-2 text-center">
      <p className="text-sm text-apple-text-secondary">
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
    <div className="flex h-80 flex-col items-center justify-center gap-3 text-center">
      <p className="text-sm text-apple-red">{getErrorMessage(error)}</p>
      {onRetry && (
        <Button
          variant="outline"
          size="sm"
          onClick={onRetry}
          className="rounded-apple-full border-apple-separator bg-apple-surface text-apple-blue hover:bg-apple-blue-pastel hover:text-apple-blue"
        >
          Повторить
        </Button>
      )}
    </div>
  );
}

function StatsTab({ filters }: { filters: BaseFilters }) {
  const period = resolvePeriod(
    filters.period,
    filters.customFrom,
    filters.customTo,
  );
  const enabled =
    filters.locationId !== null && filters.parameters.length > 0;

  const query = useQuery<WeatherStatsRow[], Error>({
    queryKey: [
      'analytics-stats',
      filters.locationId,
      filters.parameters,
      period,
      filters.source,
    ],
    queryFn: () =>
      getWeatherStats({
        location_ids: filters.locationId !== null ? [filters.locationId] : [],
        parameters: filters.parameters,
        date_from: period.date_from,
        date_to: period.date_to,
        source: filters.source,
        aggregation: 'total',
      }),
    enabled,
  });

  if (!enabled) {
    return (
      <PanelCard empty emptyMessage="Выберите локацию и параметры." />
    );
  }

  const rows = query.data ?? [];

  return (
    <PanelCard
      loading={query.isLoading}
      error={query.error ?? null}
      onRetry={() => void query.refetch()}
      empty={!query.isLoading && rows.length === 0}
    >
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Параметр</TableHead>
            <TableHead className="text-right">Min</TableHead>
            <TableHead className="text-right">Max</TableHead>
            <TableHead className="text-right">Среднее</TableHead>
            <TableHead className="text-right">Сумма</TableHead>
            <TableHead className="text-right">N</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((r) => (
            <TableRow key={`${r.parameter}-${r.time}`}>
              <TableCell className="font-medium">{r.parameter}</TableCell>
              <TableCell className="text-right tabular-nums">
                {formatNumber(r.min)}
              </TableCell>
              <TableCell className="text-right tabular-nums">
                {formatNumber(r.max)}
              </TableCell>
              <TableCell className="text-right tabular-nums">
                {formatNumber(r.mean)}
              </TableCell>
              <TableCell className="text-right tabular-nums">
                {formatNumber(r.sum)}
              </TableCell>
              <TableCell className="text-right tabular-nums">
                {r.count}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </PanelCard>
  );
}

interface AnomalyChartPoint {
  time: string;
  value: number | null;
  mean: number | null;
  upper1: number | null;
  lower1: number | null;
  upper2: number | null;
  lower2: number | null;
  moderate: number | null;
  extreme: number | null;
}

function AnomaliesTab({ filters }: { filters: BaseFilters }) {
  const period = resolvePeriod(
    filters.period,
    filters.customFrom,
    filters.customTo,
  );
  const enabled = filters.locationId !== null && Boolean(filters.parameter);

  const query = useQuery<AnomalyRow[], Error>({
    queryKey: [
      'analytics-anomalies',
      filters.locationId,
      filters.parameter,
      period,
      filters.normalPeriod,
      filters.source,
    ],
    queryFn: () =>
      getAnomalies({
        location_id: filters.locationId as number,
        parameter: filters.parameter,
        date_from: period.date_from,
        date_to: period.date_to,
        period: filters.normalPeriod,
        source: filters.source,
      }),
    enabled,
  });

  const data: AnomalyChartPoint[] = useMemo(() => {
    return (query.data ?? []).map((r) => {
      const mean = r.normal_mean;
      const std = r.normal_std;
      const upper1 = mean !== null && std !== null ? mean + std : null;
      const lower1 = mean !== null && std !== null ? mean - std : null;
      const upper2 = mean !== null && std !== null ? mean + 2 * std : null;
      const lower2 = mean !== null && std !== null ? mean - 2 * std : null;
      return {
        time: r.time,
        value: r.value,
        mean,
        upper1,
        lower1,
        upper2,
        lower2,
        moderate: r.level === 'moderate' ? r.value : null,
        extreme: r.level === 'extreme' ? r.value : null,
      };
    });
  }, [query.data]);

  if (!enabled) {
    return (
      <PanelCard empty emptyMessage="Выберите локацию и параметр." />
    );
  }

  return (
    <>
      <PanelCard
        loading={query.isLoading}
        error={query.error ?? null}
        onRetry={() => void query.refetch()}
        empty={!query.isLoading && data.length === 0}
        height={420}
      >
        <ResponsiveContainer width="100%" height={420}>
          <ComposedChart data={data}>
            <CartesianGrid
              strokeDasharray="3 3"
              stroke="var(--apple-separator)"
              opacity={1}
            />
            <XAxis
              dataKey="time"
              tick={APPLE_AXIS_TICK}
              stroke="var(--apple-separator)"
            />
            <YAxis tick={APPLE_AXIS_TICK} stroke="var(--apple-separator)" />
            <Tooltip
              contentStyle={APPLE_TOOLTIP_CONTENT}
              labelStyle={APPLE_TOOLTIP_LABEL}
              cursor={APPLE_TOOLTIP_CURSOR}
            />
            <Legend wrapperStyle={APPLE_LEGEND_STYLE} />
            <Line
              name="Норма"
              dataKey="mean"
              type="monotone"
              stroke={APPLE_CHART_COLORS.gray}
              dot={false}
              strokeWidth={1.5}
              strokeDasharray="4 4"
              isAnimationActive={false}
              connectNulls
            />
            <Line
              name="±1σ"
              dataKey="upper1"
              type="monotone"
              stroke={APPLE_CHART_COLORS.blueSoft}
              dot={false}
              strokeWidth={1}
              isAnimationActive={false}
              connectNulls
            />
            <Line
              dataKey="lower1"
              type="monotone"
              stroke={APPLE_CHART_COLORS.blueSoft}
              dot={false}
              strokeWidth={1}
              legendType="none"
              isAnimationActive={false}
              connectNulls
            />
            <Line
              name="Значение"
              dataKey="value"
              type="monotone"
              stroke={APPLE_CHART_COLORS.blue}
              dot={false}
              strokeWidth={2}
              isAnimationActive={false}
              connectNulls
            />
            <Scatter
              name="|σ| > 1"
              dataKey="moderate"
              fill={APPLE_CHART_COLORS.orange}
              shape="circle"
            />
            <Scatter
              name="|σ| > 2"
              dataKey="extreme"
              fill={APPLE_CHART_COLORS.red}
              shape="circle"
            />
          </ComposedChart>
        </ResponsiveContainer>
      </PanelCard>
      <AnomaliesLegend />
    </>
  );
}

function AnomaliesLegend() {
  return (
    <p className="text-xs text-apple-text-tertiary">
      Жёлтые точки — отклонение более 1σ; красные — более 2σ. Норма
      рассчитывается по выбранному бакету (месяц / неделя / день года).
    </p>
  );
}

function CorrelationsTab({ filters }: { filters: BaseFilters }) {
  const period = resolvePeriod(
    filters.period,
    filters.customFrom,
    filters.customTo,
  );
  const enabled =
    filters.locationId !== null && filters.parameters.length >= 2;

  const query = useQuery<CorrelationMatrix, Error>({
    queryKey: [
      'analytics-correlations',
      filters.locationId,
      filters.parameters,
      period,
      filters.source,
    ],
    queryFn: () =>
      getCorrelations({
        location_id: filters.locationId as number,
        parameters: filters.parameters,
        date_from: period.date_from,
        date_to: period.date_to,
        source: filters.source,
      }),
    enabled,
  });

  if (!enabled) {
    return (
      <PanelCard
        empty
        emptyMessage="Выберите локацию и минимум 2 параметра."
      />
    );
  }

  const matrix = query.data;

  return (
    <PanelCard
      loading={query.isLoading}
      error={query.error ?? null}
      onRetry={() => void query.refetch()}
      empty={!query.isLoading && !matrix}
      height={520}
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
          layout={plotlyLayout()}
          config={plotlyConfig()}
          useResizeHandler
          style={fillStyle}
        />
      )}
    </PanelCard>
  );
}

interface NormalsChartPoint {
  bucket: string;
  mean: number | null;
  min: number | null;
  max: number | null;
  std: number | null;
}

function NormalsTab({ filters }: { filters: BaseFilters }) {
  const enabled = filters.locationId !== null && Boolean(filters.parameter);

  const query = useQuery<ClimateNormalRow[], Error>({
    queryKey: [
      'analytics-normals',
      filters.locationId,
      filters.parameter,
      filters.normalPeriod,
    ],
    queryFn: () =>
      getClimateNormals({
        location_id: filters.locationId as number,
        parameter: filters.parameter,
        period: filters.normalPeriod,
      }),
    enabled,
  });

  const rows = query.data ?? [];
  const data: NormalsChartPoint[] = useMemo(
    () =>
      [...rows]
        .sort((a, b) => a.bucket - b.bucket)
        .map((r) => ({
          bucket: bucketLabel(r.period, r.bucket),
          mean: r.mean,
          min: r.min,
          max: r.max,
          std: r.std,
        })),
    [rows],
  );

  if (!enabled) {
    return (
      <PanelCard empty emptyMessage="Выберите локацию и параметр." />
    );
  }

  const yearFrom = rows[0]?.year_from ?? null;
  const yearTo = rows[0]?.year_to ?? null;

  return (
    <>
      <PanelCard
        loading={query.isLoading}
        error={query.error ?? null}
        onRetry={() => void query.refetch()}
        empty={!query.isLoading && data.length === 0}
        emptyMessage="Нет кэшированных норм. Сначала запустите перерасчёт (Cron 1 числа месяца) или вызовите API с refresh=true."
        height={400}
      >
        <ResponsiveContainer width="100%" height={400}>
          <ComposedChart data={data}>
            <CartesianGrid
              strokeDasharray="3 3"
              stroke="var(--apple-separator)"
              opacity={1}
            />
            <XAxis
              dataKey="bucket"
              tick={APPLE_AXIS_TICK}
              stroke="var(--apple-separator)"
            />
            <YAxis tick={APPLE_AXIS_TICK} stroke="var(--apple-separator)" />
            <Tooltip
              contentStyle={APPLE_TOOLTIP_CONTENT}
              labelStyle={APPLE_TOOLTIP_LABEL}
              cursor={{ fill: 'var(--apple-blue-pastel)', opacity: 0.4 }}
            />
            <Legend wrapperStyle={APPLE_LEGEND_STYLE} />
            <Bar
              name="Среднее"
              dataKey="mean"
              fill={APPLE_CHART_COLORS.blue}
              radius={[6, 6, 0, 0]}
              isAnimationActive={false}
            />
            <Line
              name="Min"
              dataKey="min"
              type="monotone"
              stroke={APPLE_CHART_COLORS.teal}
              dot={false}
              strokeWidth={1.5}
              isAnimationActive={false}
              connectNulls
            />
            <Line
              name="Max"
              dataKey="max"
              type="monotone"
              stroke={APPLE_CHART_COLORS.red}
              dot={false}
              strokeWidth={1.5}
              isAnimationActive={false}
              connectNulls
            />
          </ComposedChart>
        </ResponsiveContainer>
      </PanelCard>
      <NormalsTable
        rows={rows}
        period={filters.normalPeriod}
        yearFrom={yearFrom}
        yearTo={yearTo}
      />
    </>
  );
}

function NormalsTable(props: {
  rows: ClimateNormalRow[];
  period: NormalPeriod;
  yearFrom: number | null;
  yearTo: number | null;
}) {
  if (props.rows.length === 0) return null;
  const sorted = [...props.rows].sort((a, b) => a.bucket - b.bucket);

  return (
    <Card className="rounded-apple-lg border-0 bg-apple-surface shadow-apple-md">
      <CardContent className="flex flex-col gap-3 p-6 md:p-8">
        <div className="flex items-baseline justify-between">
          <h2 className="text-sm font-medium text-apple-text">
            Климатические нормы
          </h2>
          <span className="text-xs text-apple-text-tertiary">
            {props.yearFrom && props.yearTo
              ? `Базовый период: ${props.yearFrom}–${props.yearTo}`
              : 'Базовый период не определён'}
          </span>
        </div>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Бакет</TableHead>
              <TableHead className="text-right">Среднее</TableHead>
              <TableHead className="text-right">σ</TableHead>
              <TableHead className="text-right">Min</TableHead>
              <TableHead className="text-right">Max</TableHead>
              <TableHead className="text-right">N</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {sorted.map((r) => (
              <TableRow key={`${r.period}-${r.bucket}`}>
                <TableCell className="font-medium">
                  {bucketLabel(r.period, r.bucket)}
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {formatNumber(r.mean)}
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {formatNumber(r.std)}
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {formatNumber(r.min)}
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {formatNumber(r.max)}
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {r.count}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}

const fillStyle: CSSProperties = { width: '100%', height: '100%' };

const APPLE_TOOLTIP_CONTENT: CSSProperties = {
  background: 'var(--apple-surface-elevated)',
  border: 'none',
  borderRadius: 'var(--apple-radius-md)',
  boxShadow: 'var(--apple-shadow-lg)',
  fontSize: 12,
  color: 'var(--apple-text-primary)',
  padding: '8px 12px',
};

const APPLE_TOOLTIP_LABEL: CSSProperties = {
  color: 'var(--apple-text-secondary)',
  fontSize: 11,
  marginBottom: 4,
};

const APPLE_TOOLTIP_CURSOR = {
  stroke: 'var(--apple-separator)',
  strokeWidth: 1,
};

const APPLE_AXIS_TICK = {
  fontSize: 12,
  fill: 'var(--apple-text-secondary)',
};

const APPLE_LEGEND_STYLE: CSSProperties = {
  fontSize: 12,
  color: 'var(--apple-text-secondary)',
};

const APPLE_CHART_COLORS = {
  blue: '#007AFF',
  teal: '#5AC8FA',
  green: '#34C759',
  orange: '#FF9500',
  red: '#FF3B30',
  purple: '#AF52DE',
  gray: '#8E8E93',
  blueSoft: 'rgba(0, 122, 255, 0.28)',
};

function plotlyLayout() {
  return {
    autosize: true,
    margin: { l: 100, r: 30, t: 20, b: 80 },
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    xaxis: { title: { text: '' }, automargin: true },
    yaxis: { title: { text: '' }, automargin: true },
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

export default AnalyticsPage;
