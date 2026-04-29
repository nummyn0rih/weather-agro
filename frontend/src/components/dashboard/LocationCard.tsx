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
    <Card>
      <CardHeader className="space-y-1">
        <div className="flex items-start justify-between gap-2">
          <CardTitle className="text-lg">
            <Link
              to={`/locations`}
              className="hover:underline"
              aria-label={`Перейти к локации ${location.name}`}
            >
              {location.name}
            </Link>
          </CardTitle>
          <span className="text-xs text-muted-foreground">
            {location.region ?? '—'}
          </span>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {loading ? (
          <CardSkeleton />
        ) : importPending ? (
          <p className="text-sm text-muted-foreground">
            Идёт загрузка истории — данные появятся после завершения импорта.
          </p>
        ) : chartPoints.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Нет данных за последние 7 дней.
          </p>
        ) : (
          <>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <div className="text-xs text-muted-foreground">
                  Текущая температура
                </div>
                <div className="text-2xl font-semibold tabular-nums">
                  {formatTemp(last?.temp_avg)}
                </div>
                <div className="text-xs text-muted-foreground">
                  на {last?.time ?? '—'}
                </div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">
                  Осадки за сегодня
                </div>
                <div className="text-2xl font-semibold tabular-nums">
                  {formatPrecip(last?.precipitation)}
                </div>
                <div className="text-xs text-muted-foreground">
                  на {last?.time ?? '—'}
                </div>
              </div>
            </div>
            <div className="h-24">
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
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-2">
          <Skeleton className="h-3 w-2/3" />
          <Skeleton className="h-7 w-3/4" />
        </div>
        <div className="space-y-2">
          <Skeleton className="h-3 w-2/3" />
          <Skeleton className="h-7 w-3/4" />
        </div>
      </div>
      <Skeleton className="h-24 w-full" />
    </div>
  );
}

export default LocationCard;
