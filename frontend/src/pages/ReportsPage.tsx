import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import axios from 'axios';
import { Download, FileText, Trash2 } from 'lucide-react';
import { useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Progress } from '@/components/ui/progress';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { type Location, listLocations } from '@/lib/locations-api';
import {
  type Report,
  type ReportStatus,
  deleteReport,
  downloadReport,
  generateReport,
  listReports,
} from '@/lib/reports-api';

const POLL_INTERVAL_MS = 3000;
const MIN_YEAR = 2000;

const STATUS_LABEL: Record<ReportStatus, string> = {
  pending: 'В очереди',
  in_progress: 'Генерация…',
  done: 'Готов',
  error: 'Ошибка',
};

function getErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data as
      | { detail?: string | { msg?: string }[] }
      | undefined;
    const detail = data?.detail;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail) && detail.length > 0) {
      const first = detail[0];
      if (first?.msg) return first.msg;
    }
    return error.message;
  }
  return error instanceof Error ? error.message : 'Неизвестная ошибка';
}

function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString('ru-RU');
}

function formatBytes(bytes: number | null): string {
  if (bytes === null) return '—';
  if (bytes < 1024) return `${bytes} Б`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} КБ`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} МБ`;
}

function yearOptions(): number[] {
  const current = new Date().getFullYear();
  const list: number[] = [];
  for (let y = current; y >= MIN_YEAR; y--) list.push(y);
  return list;
}

export function ReportsPage() {
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();

  const locationParam = searchParams.get('location') ?? '';
  const yearParam =
    searchParams.get('year') ?? String(new Date().getFullYear());

  const locationsQuery = useQuery<Location[], Error>({
    queryKey: ['locations'],
    queryFn: () => listLocations(),
  });

  const reportsQuery = useQuery<Report[], Error>({
    queryKey: ['reports'],
    queryFn: () => listReports(),
    refetchInterval: (q) => {
      const data = q.state.data;
      if (!data) return false;
      const hasPending = data.some(
        (r) => r.status === 'pending' || r.status === 'in_progress',
      );
      return hasPending ? POLL_INTERVAL_MS : false;
    },
  });

  const locationName = useMemo(() => {
    const map = new Map<number, string>();
    for (const loc of locationsQuery.data ?? []) map.set(loc.id, loc.name);
    return map;
  }, [locationsQuery.data]);

  const sortedReports = useMemo(() => {
    if (!reportsQuery.data) return [];
    return [...reportsQuery.data].sort((a, b) =>
      a.created_at < b.created_at ? 1 : a.created_at > b.created_at ? -1 : 0,
    );
  }, [reportsQuery.data]);

  const [formError, setFormError] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Report | null>(null);
  const [downloadingId, setDownloadingId] = useState<number | null>(null);
  const [downloadError, setDownloadError] = useState<string | null>(null);

  const generateMutation = useMutation({
    mutationFn: generateReport,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['reports'] });
      setFormError(null);
    },
    onError: (error) => setFormError(getErrorMessage(error)),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteReport(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['reports'] });
      setDeleteTarget(null);
    },
  });

  function setParam(key: string, value: string | null) {
    const params = new URLSearchParams(searchParams);
    if (value === null || value === '') {
      params.delete(key);
    } else {
      params.set(key, value);
    }
    setSearchParams(params, { replace: true });
  }

  function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!locationParam) {
      setFormError('Выберите локацию');
      return;
    }
    const locationId = Number(locationParam);
    const year = Number(yearParam);
    if (!Number.isFinite(locationId)) {
      setFormError('Неверная локация');
      return;
    }
    if (!Number.isFinite(year) || year < MIN_YEAR) {
      setFormError('Неверный год');
      return;
    }
    setFormError(null);
    generateMutation.mutate({ location_id: locationId, season_year: year });
  }

  async function handleDownload(report: Report) {
    setDownloadError(null);
    setDownloadingId(report.id);
    try {
      await downloadReport(report.id);
    } catch (error) {
      setDownloadError(getErrorMessage(error));
    } finally {
      setDownloadingId(null);
    }
  }

  const isGenerating = generateMutation.isPending;
  const years = yearOptions();

  return (
    <div className="flex h-full flex-col gap-6 p-4 sm:p-6 md:p-8">
      <header className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold tracking-tight">Отчёты</h1>
        <p className="text-sm text-muted-foreground">
          Сезонный PDF-отчёт по локации: погода, аномалии, события, урожайность.
        </p>
      </header>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Сгенерировать отчёт</CardTitle>
          <CardDescription>
            Выберите локацию и год. Генерация занимает до нескольких минут.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form
            className="grid gap-4 sm:grid-cols-[1fr_auto_auto] sm:items-end"
            onSubmit={handleSubmit}
          >
            <div className="grid gap-1.5">
              <Label htmlFor="rep-location">Локация</Label>
              <Select
                value={locationParam}
                onValueChange={(v) => setParam('location', v)}
              >
                <SelectTrigger id="rep-location">
                  <SelectValue placeholder="Выберите локацию" />
                </SelectTrigger>
                <SelectContent>
                  {locationsQuery.data?.map((loc) => (
                    <SelectItem key={loc.id} value={String(loc.id)}>
                      {loc.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="rep-year">Сезон (год)</Label>
              <Select
                value={yearParam}
                onValueChange={(v) => setParam('year', v)}
              >
                <SelectTrigger id="rep-year" className="min-w-[120px]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {years.map((y) => (
                    <SelectItem key={y} value={String(y)}>
                      {y}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <Button type="submit" disabled={isGenerating}>
              {isGenerating ? 'Запуск…' : 'Сгенерировать'}
            </Button>
          </form>
          {formError && (
            <p className="mt-3 text-sm text-destructive" role="alert">
              {formError}
            </p>
          )}
        </CardContent>
      </Card>

      <section className="flex flex-col gap-3">
        <h2 className="text-lg font-semibold">Ранее сгенерированные</h2>

        {downloadError && (
          <p className="text-sm text-destructive" role="alert">
            {downloadError}
          </p>
        )}

        {reportsQuery.isLoading ? (
          <LoadingState />
        ) : reportsQuery.isError ? (
          <ErrorState
            message={getErrorMessage(reportsQuery.error)}
            onRetry={() => void reportsQuery.refetch()}
          />
        ) : sortedReports.length === 0 ? (
          <EmptyState message="Отчётов пока нет. Запустите первую генерацию выше." />
        ) : (
          <div className="flex flex-col gap-3">
            {sortedReports.map((report) => (
              <ReportRow
                key={report.id}
                report={report}
                locationLabel={
                  report.location_id === null
                    ? `Локация #—`
                    : (locationName.get(report.location_id) ??
                      `Локация #${report.location_id}`)
                }
                onDownload={() => void handleDownload(report)}
                onDelete={() => setDeleteTarget(report)}
                isDownloading={downloadingId === report.id}
              />
            ))}
          </div>
        )}
      </section>

      <AlertDialog
        open={deleteTarget !== null}
        onOpenChange={(open) => {
          if (!open) setDeleteTarget(null);
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Удалить отчёт?</AlertDialogTitle>
            <AlertDialogDescription>
              Запись и PDF-файл будут удалены без возможности восстановления.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleteMutation.isPending}>
              Отмена
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={(e) => {
                e.preventDefault();
                if (deleteTarget) deleteMutation.mutate(deleteTarget.id);
              }}
              disabled={deleteMutation.isPending}
            >
              {deleteMutation.isPending ? 'Удаление…' : 'Удалить'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

function ReportRow({
  report,
  locationLabel,
  onDownload,
  onDelete,
  isDownloading,
}: {
  report: Report;
  locationLabel: string;
  onDownload: () => void;
  onDelete: () => void;
  isDownloading: boolean;
}) {
  const isPending =
    report.status === 'pending' || report.status === 'in_progress';
  const isDone = report.status === 'done';
  const isError = report.status === 'error';

  return (
    <Card>
      <CardHeader className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-start gap-3">
          <FileText
            className="mt-0.5 h-5 w-5 shrink-0 text-muted-foreground"
            aria-hidden
          />
          <div className="flex flex-col gap-1">
            <CardTitle className="text-base">
              {locationLabel} · сезон {report.season_year}
            </CardTitle>
            <CardDescription>
              Создан {formatDateTime(report.created_at)}
              {report.finished_at &&
                ` · завершён ${formatDateTime(report.finished_at)}`}
            </CardDescription>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span
            className={
              isError
                ? 'text-xs text-destructive'
                : 'text-xs text-muted-foreground'
            }
          >
            {STATUS_LABEL[report.status]}
            {isDone && ` · ${formatBytes(report.file_size_bytes)}`}
          </span>
          <Button
            variant="outline"
            size="sm"
            onClick={onDownload}
            disabled={!isDone || isDownloading}
          >
            <Download className="h-4 w-4" />
            {isDownloading ? 'Загрузка…' : 'Скачать'}
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={onDelete}
            disabled={isPending}
          >
            <Trash2 className="h-4 w-4" />
            Удалить
          </Button>
        </div>
      </CardHeader>
      {isPending && (
        <CardContent>
          <Progress />
          <p className="mt-2 text-xs text-muted-foreground">
            Идёт генерация. Список обновляется автоматически.
          </p>
        </CardContent>
      )}
      {isError && report.error && (
        <CardContent>
          <p className="text-sm text-destructive">{report.error}</p>
        </CardContent>
      )}
    </Card>
  );
}

function LoadingState() {
  return (
    <div className="flex flex-col gap-3 p-6">
      <div className="h-4 w-1/3 animate-pulse rounded bg-muted" />
      <div className="h-20 w-full animate-pulse rounded bg-muted" />
      <div className="h-20 w-full animate-pulse rounded bg-muted" />
    </div>
  );
}

function ErrorState({
  message,
  onRetry,
}: {
  message: string;
  onRetry: () => void;
}) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-md border p-10 text-center">
      <p className="text-sm text-destructive">{message}</p>
      <Button variant="outline" size="sm" onClick={onRetry}>
        Повторить
      </Button>
    </div>
  );
}

function EmptyState({ message }: { message: string }) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-md border p-12 text-center">
      <p className="text-sm text-muted-foreground">{message}</p>
    </div>
  );
}

export default ReportsPage;
