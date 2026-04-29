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
    <Card>
      <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between space-y-0">
        <div className="flex items-center gap-2">
          <CalendarDays className="h-4 w-4 text-muted-foreground" aria-hidden />
          <CardTitle className="text-base">Прогноз 7 дней</CardTitle>
        </div>
        {locations.length > 0 && (
          <Select
            value={selectedId !== null ? String(selectedId) : undefined}
            onValueChange={(value) => setSelectedId(Number(value))}
          >
            <SelectTrigger className="w-full sm:w-64">
              <SelectValue placeholder="Локация" />
            </SelectTrigger>
            <SelectContent>
              {locations.map((loc) => (
                <SelectItem key={loc.id} value={String(loc.id)}>
                  {loc.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
      </CardHeader>
      <CardContent>
        {locations.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Добавьте локацию, чтобы увидеть прогноз.
          </p>
        ) : query.isLoading ? (
          <ForecastSkeleton />
        ) : query.isError ? (
          <p className="text-sm text-destructive">
            Не удалось загрузить прогноз: {query.error.message}
          </p>
        ) : sortedPoints.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Прогнозные данные пока недоступны.
          </p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Дата</TableHead>
                <TableHead className="text-right">T min</TableHead>
                <TableHead className="text-right">T avg</TableHead>
                <TableHead className="text-right">T max</TableHead>
                <TableHead className="text-right">Осадки</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {sortedPoints.map((point) => (
                <TableRow key={point.time}>
                  <TableCell className="font-mono text-xs">
                    {point.time}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {formatNumber(point.temp_min, '°C')}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {formatNumber(point.temp_avg, '°C')}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {formatNumber(point.temp_max, '°C')}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {formatNumber(point.precipitation, 'мм')}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}

function ForecastSkeleton() {
  return (
    <div className="space-y-2">
      {Array.from({ length: 5 }).map((_, idx) => (
        <Skeleton key={idx} className="h-8 w-full" />
      ))}
    </div>
  );
}

export default ForecastBlock;
