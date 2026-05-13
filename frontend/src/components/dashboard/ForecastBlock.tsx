import { useQuery } from '@tanstack/react-query';
import { CalendarDays } from 'lucide-react';
import { useEffect, useState } from 'react';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
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
import type { Location } from '@/lib/locations-api';
import {
  type WeatherDailyPoint,
  getWeatherDaily,
} from '@/lib/weather-api';

const FORECAST_PARAMETERS = [
  'temp_min',
  'temp_max',
  'temp_avg',
  'precipitation',
];

interface ForecastBlockProps {
  locations: Location[];
}

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

function addDaysIso(iso: string, days: number): string {
  const d = new Date(`${iso}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}

function formatNumber(
  value: WeatherDailyPoint[string] | undefined,
  unit: string,
  digits = 1,
): string {
  if (typeof value !== 'number') return '—';
  return `${value.toFixed(digits)} ${unit}`;
}

export function ForecastBlock({ locations }: ForecastBlockProps) {
  const [selectedId, setSelectedId] = useState<number | null>(
    locations[0]?.id ?? null,
  );

  useEffect(() => {
    if (locations.length === 0) {
      setSelectedId(null);
      return;
    }
    if (selectedId === null || !locations.some((l) => l.id === selectedId)) {
      setSelectedId(locations[0].id);
    }
  }, [locations, selectedId]);

  const dateFrom = todayIso();
  const dateTo = addDaysIso(dateFrom, 6);

  const query = useQuery<WeatherDailyPoint[], Error>({
    queryKey: ['forecast', selectedId, dateFrom, dateTo],
    enabled: selectedId !== null,
    queryFn: () =>
      getWeatherDaily({
        location_ids: [selectedId as number],
        parameters: FORECAST_PARAMETERS,
        date_from: dateFrom,
        date_to: dateTo,
        source: 'average',
      }),
  });

  const sortedPoints = (query.data ?? [])
    .slice()
    .sort((a, b) => a.time.localeCompare(b.time));

  return (
    <Card className="rounded-apple-lg border-0 bg-apple-surface text-apple-text shadow-apple-md transition-shadow duration-300 ease-apple hover:shadow-apple-lg">
      <CardHeader className="flex flex-col gap-3 space-y-0 p-7 pb-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <span className="flex h-9 w-9 items-center justify-center rounded-apple-full bg-apple-blue-pastel text-apple-blue">
            <CalendarDays className="h-4 w-4" aria-hidden />
          </span>
          <CardTitle className="text-lg font-semibold tracking-apple-tight">
            Прогноз 7 дней
          </CardTitle>
        </div>
        {locations.length > 0 && (
          <Select
            value={selectedId !== null ? String(selectedId) : undefined}
            onValueChange={(value) => setSelectedId(Number(value))}
          >
            <SelectTrigger className="w-full rounded-apple-full border-apple-separator bg-apple-bg text-sm text-apple-text shadow-none transition-colors hover:bg-apple-blue-pastel/40 focus:ring-apple-blue sm:w-64">
              <SelectValue placeholder="Локация" />
            </SelectTrigger>
            <SelectContent className="rounded-apple-md border-apple-separator bg-apple-surface text-apple-text shadow-apple-lg">
              {locations.map((loc) => (
                <SelectItem
                  key={loc.id}
                  value={String(loc.id)}
                  className="rounded-apple-sm focus:bg-apple-blue-pastel focus:text-apple-blue"
                >
                  {loc.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
      </CardHeader>
      <CardContent className="p-7 pt-0">
        {locations.length === 0 ? (
          <p className="text-sm text-apple-text-secondary">
            Добавьте локацию, чтобы увидеть прогноз.
          </p>
        ) : query.isLoading ? (
          <ForecastSkeleton />
        ) : query.isError ? (
          <p className="text-sm text-apple-red">
            Не удалось загрузить прогноз: {query.error.message}
          </p>
        ) : sortedPoints.length === 0 ? (
          <p className="text-sm text-apple-text-secondary">
            Прогнозные данные пока недоступны.
          </p>
        ) : (
          <div className="overflow-hidden rounded-apple-md bg-apple-bg/60">
            <Table>
              <TableHeader>
                <TableRow className="border-b-apple-separator hover:bg-transparent">
                  <TableHead className="text-apple-text-tertiary">Дата</TableHead>
                  <TableHead className="text-right text-apple-text-tertiary">T min</TableHead>
                  <TableHead className="text-right text-apple-text-tertiary">T avg</TableHead>
                  <TableHead className="text-right text-apple-text-tertiary">T max</TableHead>
                  <TableHead className="text-right text-apple-text-tertiary">Осадки</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {sortedPoints.map((point) => (
                  <TableRow
                    key={point.time}
                    className="border-b-apple-separator transition-colors last:border-b-0 hover:bg-apple-blue-pastel/30"
                  >
                    <TableCell className="font-mono text-xs text-apple-text-secondary">
                      {point.time}
                    </TableCell>
                    <TableCell className="text-right tabular-nums text-apple-text">
                      {formatNumber(point.temp_min, '°C')}
                    </TableCell>
                    <TableCell className="text-right tabular-nums font-medium text-apple-text">
                      {formatNumber(point.temp_avg, '°C')}
                    </TableCell>
                    <TableCell className="text-right tabular-nums text-apple-text">
                      {formatNumber(point.temp_max, '°C')}
                    </TableCell>
                    <TableCell className="text-right tabular-nums text-apple-teal">
                      {formatNumber(point.precipitation, 'мм')}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function ForecastSkeleton() {
  return (
    <div className="space-y-2">
      {Array.from({ length: 5 }).map((_, idx) => (
        <Skeleton key={idx} className="h-8 w-full rounded-apple-sm bg-apple-bg" />
      ))}
    </div>
  );
}

export default ForecastBlock;
