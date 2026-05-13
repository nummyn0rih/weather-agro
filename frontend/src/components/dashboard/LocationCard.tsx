import { Link } from 'react-router-dom';
import {
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import type { Location } from '@/lib/locations-api';
import type { WeatherDailyPoint } from '@/lib/weather-api';

interface LocationCardProps {
  location: Location;
  points: WeatherDailyPoint[];
  loading: boolean;
}

interface ChartPoint {
  time: string;
  label: string;
  temp_avg: number | null;
  precipitation: number | null;
}

function toChartPoints(points: WeatherDailyPoint[]): ChartPoint[] {
  return [...points]
    .sort((a, b) => a.time.localeCompare(b.time))
    .map((p) => ({
      time: p.time,
      label: p.time.slice(5),
      temp_avg: typeof p.temp_avg === 'number' ? p.temp_avg : null,
      precipitation:
        typeof p.precipitation === 'number' ? p.precipitation : null,
    }));
}

function formatTemp(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—';
  return `${value.toFixed(1)} °C`;
}

function formatPrecip(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—';
  return `${value.toFixed(1)} мм`;
}

export function LocationCard({
  location,
  points,
  loading,
}: LocationCardProps) {
  const chartPoints = toChartPoints(points);
  const last = chartPoints.at(-1);
  const importPending =
    location.import_status === 'pending' ||
    location.import_status === 'in_progress';

  return (
    <Card className="group rounded-apple-lg border-0 bg-apple-surface text-apple-text shadow-apple-md transition-all duration-300 ease-apple hover:-translate-y-0.5 hover:shadow-apple-lg">
      <CardHeader className="space-y-1 p-7 pb-3">
        <div className="flex items-start justify-between gap-2">
          <CardTitle className="text-xl font-semibold tracking-apple-tight">
            <Link
              to={`/locations`}
              className="rounded-apple-sm decoration-apple-blue/40 underline-offset-4 transition-colors hover:text-apple-blue hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-apple-blue focus-visible:ring-offset-2 focus-visible:ring-offset-apple-surface"
              aria-label={`Перейти к локации ${location.name}`}
            >
              {location.name}
            </Link>
          </CardTitle>
          <span className="rounded-apple-full bg-apple-bg px-2.5 py-1 text-xs font-medium text-apple-text-secondary">
            {location.region ?? '—'}
          </span>
        </div>
      </CardHeader>
      <CardContent className="space-y-5 p-7 pt-0">
        {loading ? (
          <CardSkeleton />
        ) : importPending ? (
          <p className="text-sm text-apple-text-secondary">
            Идёт загрузка истории — данные появятся после завершения импорта.
          </p>
        ) : chartPoints.length === 0 ? (
          <p className="text-sm text-apple-text-secondary">
            Нет данных за последние 7 дней.
          </p>
        ) : (
          <>
            <div className="grid grid-cols-2 gap-4">
              <div className="rounded-apple-md bg-apple-orange-pastel/60 p-4">
                <div className="text-xs font-medium uppercase tracking-wide text-apple-text-tertiary">
                  Текущая температура
                </div>
                <div className="mt-1 text-3xl font-bold tabular-nums tracking-apple-tight text-apple-orange">
                  {formatTemp(last?.temp_avg)}
                </div>
                <div className="mt-0.5 text-xs text-apple-text-secondary">
                  на {last?.time ?? '—'}
                </div>
              </div>
              <div className="rounded-apple-md bg-apple-teal-pastel/60 p-4">
                <div className="text-xs font-medium uppercase tracking-wide text-apple-text-tertiary">
                  Осадки за сегодня
                </div>
                <div className="mt-1 text-3xl font-bold tabular-nums tracking-apple-tight text-apple-teal">
                  {formatPrecip(last?.precipitation)}
                </div>
                <div className="mt-0.5 text-xs text-apple-text-secondary">
                  на {last?.time ?? '—'}
                </div>
              </div>
            </div>
            <div className="h-24 text-apple-blue">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart
                  data={chartPoints}
                  margin={{ top: 4, right: 4, left: 0, bottom: 0 }}
                >
                  <XAxis
                    dataKey="label"
                    tick={{ fontSize: 10 }}
                    tickLine={false}
                    axisLine={false}
                  />
                  <YAxis
                    width={28}
                    tick={{ fontSize: 10 }}
                    tickLine={false}
                    axisLine={false}
                  />
                  <Tooltip
                    formatter={(value) =>
                      typeof value === 'number'
                        ? [`${value.toFixed(1)} °C`, 'Темп.']
                        : ['—', 'Темп.']
                    }
                    labelFormatter={(label) => `Дата: ${String(label)}`}
                  />
                  <Line
                    type="monotone"
                    dataKey="temp_avg"
                    stroke="currentColor"
                    strokeWidth={2}
                    dot={false}
                    isAnimationActive={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}

function CardSkeleton() {
  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2 rounded-apple-md bg-apple-bg p-4">
          <Skeleton className="h-3 w-2/3 rounded-apple-sm bg-apple-surface" />
          <Skeleton className="h-8 w-3/4 rounded-apple-sm bg-apple-surface" />
        </div>
        <div className="space-y-2 rounded-apple-md bg-apple-bg p-4">
          <Skeleton className="h-3 w-2/3 rounded-apple-sm bg-apple-surface" />
          <Skeleton className="h-8 w-3/4 rounded-apple-sm bg-apple-surface" />
        </div>
      </div>
      <Skeleton className="h-24 w-full rounded-apple-md bg-apple-bg" />
    </div>
  );
}

export default LocationCard;
