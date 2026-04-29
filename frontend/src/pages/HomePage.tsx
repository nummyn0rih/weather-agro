import { useQueries, useQuery } from '@tanstack/react-query';
import axios from 'axios';
import { useMemo } from 'react';
import { Link } from 'react-router-dom';

import { AlertsBlock } from '@/components/dashboard/AlertsBlock';
import { ForecastBlock } from '@/components/dashboard/ForecastBlock';
import { LocationCard } from '@/components/dashboard/LocationCard';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { type Location, listLocations } from '@/lib/locations-api';
import {
  type WeatherDailyPoint,
  getWeatherDaily,
} from '@/lib/weather-api';

const CARD_PARAMETERS = ['temp_avg', 'precipitation'];
const HISTORY_DAYS = 7;

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

function addDaysIso(iso: string, days: number): string {
  const d = new Date(`${iso}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}

function getErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data as { detail?: string } | undefined;
    if (typeof data?.detail === 'string') return data.detail;
    return error.message;
  }
  return error instanceof Error ? error.message : 'Неизвестная ошибка';
}

export function HomePage() {
  const dateTo = todayIso();
  const dateFrom = addDaysIso(dateTo, -(HISTORY_DAYS - 1));

  const locationsQuery = useQuery<Location[], Error>({
    queryKey: ['locations'],
    queryFn: () => listLocations(),
  });

  const locations = useMemo(() => {
    if (!locationsQuery.data) return [];
    return [...locationsQuery.data].sort((a, b) =>
      a.name.localeCompare(b.name, 'ru'),
    );
  }, [locationsQuery.data]);

  const weatherQueries = useQueries({
    queries: locations.map((loc) => ({
      queryKey: ['weather', 'card', loc.id, dateFrom, dateTo],
      enabled: loc.import_status === 'done',
      queryFn: () =>
        getWeatherDaily({
          location_ids: [loc.id],
          parameters: CARD_PARAMETERS,
          date_from: dateFrom,
          date_to: dateTo,
          source: 'average',
        }),
    })),
  });

  return (
    <div className="flex h-full flex-col gap-6 p-6 md:p-8">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Дашборд</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Сводка по локациям и активным алертам.
        </p>
      </header>

      {locationsQuery.isLoading ? (
        <CardsGridSkeleton />
      ) : locationsQuery.isError ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 p-10 text-center">
            <p className="text-sm text-destructive">
              {getErrorMessage(locationsQuery.error)}
            </p>
            <Button
              variant="outline"
              size="sm"
              onClick={() => void locationsQuery.refetch()}
            >
              Повторить
            </Button>
          </CardContent>
        </Card>
      ) : locations.length === 0 ? (
        <EmptyLocations />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {locations.map((loc, idx) => {
            const q = weatherQueries[idx];
            const points: WeatherDailyPoint[] = q?.data ?? [];
            const loading =
              loc.import_status === 'done' && (q?.isLoading ?? false);
            return (
              <LocationCard
                key={loc.id}
                location={loc}
                points={points}
                loading={loading}
              />
            );
          })}
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <AlertsBlock />
        <ForecastBlock locations={locations} />
      </div>
    </div>
  );
}

function CardsGridSkeleton() {
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
      {Array.from({ length: 3 }).map((_, idx) => (
        <Card key={idx}>
          <CardContent className="space-y-4 p-6">
            <Skeleton className="h-5 w-1/2" />
            <div className="grid grid-cols-2 gap-3">
              <Skeleton className="h-12 w-full" />
              <Skeleton className="h-12 w-full" />
            </div>
            <Skeleton className="h-24 w-full" />
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

function EmptyLocations() {
  return (
    <Card>
      <CardContent className="flex flex-col items-center gap-3 p-10 text-center">
        <p className="text-sm text-muted-foreground">
          Локаций пока нет. Добавьте первую, чтобы увидеть сводку.
        </p>
        <Button asChild size="sm">
          <Link to="/locations">К локациям</Link>
        </Button>
      </CardContent>
    </Card>
  );
}

export default HomePage;
