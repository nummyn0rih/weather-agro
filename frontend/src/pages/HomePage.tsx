import { useQueries, useQuery } from '@tanstack/react-query';
import axios from 'axios';
import { useMemo } from 'react';
import { Link } from 'react-router-dom';

import { AlertsBlock } from '@/components/dashboard/AlertsBlock';
import { ForecastBlock } from '@/components/dashboard/ForecastBlock';
import { LocationCard } from '@/components/dashboard/LocationCard';
import { StaggerGroup, StaggerItem } from '@/components/motion/Stagger';
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
    <div className="surface-apple flex h-full flex-col gap-8 p-6 md:gap-10 md:p-10">
      <header>
        <h1 className="text-display-sm font-semibold tracking-apple-tight text-apple-text">
          Дашборд
        </h1>
        <p className="mt-2 text-base text-apple-text-secondary">
          Сводка по локациям и активным алертам.
        </p>
      </header>

      {locationsQuery.isLoading ? (
        <CardsGridSkeleton />
      ) : locationsQuery.isError ? (
        <Card className="rounded-apple-lg border-0 bg-apple-surface text-apple-text shadow-apple-md">
          <CardContent className="flex flex-col items-center gap-3 p-10 text-center">
            <p className="text-sm text-apple-red">
              {getErrorMessage(locationsQuery.error)}
            </p>
            <Button
              variant="outline"
              size="sm"
              onClick={() => void locationsQuery.refetch()}
              className="rounded-apple-full border-apple-separator bg-apple-surface text-apple-blue hover:bg-apple-blue-pastel hover:text-apple-blue"
            >
              Повторить
            </Button>
          </CardContent>
        </Card>
      ) : locations.length === 0 ? (
        <EmptyLocations />
      ) : (
        <StaggerGroup className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
          {locations.map((loc, idx) => {
            const q = weatherQueries[idx];
            const points: WeatherDailyPoint[] = q?.data ?? [];
            const loading =
              loc.import_status === 'done' && (q?.isLoading ?? false);
            return (
              <StaggerItem key={loc.id}>
                <LocationCard
                  location={loc}
                  points={points}
                  loading={loading}
                />
              </StaggerItem>
            );
          })}
        </StaggerGroup>
      )}

      <StaggerGroup className="grid gap-5 lg:grid-cols-2">
        <StaggerItem>
          <AlertsBlock />
        </StaggerItem>
        <StaggerItem>
          <ForecastBlock locations={locations} />
        </StaggerItem>
      </StaggerGroup>
    </div>
  );
}

function CardsGridSkeleton() {
  return (
    <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
      {Array.from({ length: 3 }).map((_, idx) => (
        <Card
          key={idx}
          className="rounded-apple-lg border-0 bg-apple-surface shadow-apple-md"
        >
          <CardContent className="space-y-5 p-7">
            <Skeleton className="h-5 w-1/2 rounded-apple-sm bg-apple-bg" />
            <div className="grid grid-cols-2 gap-3">
              <Skeleton className="h-14 w-full rounded-apple-sm bg-apple-bg" />
              <Skeleton className="h-14 w-full rounded-apple-sm bg-apple-bg" />
            </div>
            <Skeleton className="h-24 w-full rounded-apple-md bg-apple-bg" />
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

function EmptyLocations() {
  return (
    <Card className="rounded-apple-lg border-0 bg-apple-surface text-apple-text shadow-apple-md">
      <CardContent className="flex flex-col items-center gap-3 p-10 text-center">
        <p className="text-sm text-apple-text-secondary">
          Локаций пока нет. Добавьте первую, чтобы увидеть сводку.
        </p>
        <Button
          asChild
          size="sm"
          className="rounded-apple-full bg-apple-blue px-5 text-white shadow-apple-sm transition-all duration-200 ease-apple hover:bg-apple-blue-hover hover:shadow-apple-md"
        >
          <Link to="/locations">К локациям</Link>
        </Button>
      </CardContent>
    </Card>
  );
}

export default HomePage;
