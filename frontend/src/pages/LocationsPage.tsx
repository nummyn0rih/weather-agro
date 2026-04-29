import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import axios from 'axios';
import { Plus } from 'lucide-react';
import { useMemo, useState } from 'react';

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
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Progress } from '@/components/ui/progress';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Textarea } from '@/components/ui/textarea';
import {
  type Location,
  type LocationCreateInput,
  type LocationType,
  createLocation,
  deleteLocation,
  listLocations,
  updateLocation,
} from '@/lib/locations-api';

const POLL_INTERVAL_MS = 5000;

const TYPE_LABEL: Record<LocationType, string> = {
  own: 'Своя',
  purchase: 'Закупка',
};

const STATUS_LABEL: Record<Location['import_status'], string> = {
  pending: 'Ожидание',
  in_progress: 'Загрузка',
  done: 'Готово',
  error: 'Ошибка',
};

interface FormState {
  name: string;
  latitude: string;
  longitude: string;
  region: string;
  type: LocationType;
  note: string;
}

const EMPTY_FORM: FormState = {
  name: '',
  latitude: '',
  longitude: '',
  region: '',
  type: 'own',
  note: '',
};

function toFormState(location: Location): FormState {
  return {
    name: location.name,
    latitude: String(location.latitude),
    longitude: String(location.longitude),
    region: location.region ?? '',
    type: location.type,
    note: location.note ?? '',
  };
}

function parseFormState(form: FormState): LocationCreateInput | string {
  if (form.name.trim().length === 0) return 'Укажите название';
  const lat = Number(form.latitude);
  const lon = Number(form.longitude);
  if (!Number.isFinite(lat) || lat < -90 || lat > 90) {
    return 'Широта должна быть числом от -90 до 90';
  }
  if (!Number.isFinite(lon) || lon < -180 || lon > 180) {
    return 'Долгота должна быть числом от -180 до 180';
  }
  return {
    name: form.name.trim(),
    latitude: lat,
    longitude: lon,
    region: form.region.trim() === '' ? null : form.region.trim(),
    type: form.type,
    note: form.note.trim() === '' ? null : form.note.trim(),
  };
}

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

export function LocationsPage() {
  const queryClient = useQueryClient();

  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Location | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [formError, setFormError] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Location | null>(null);

  const query = useQuery<Location[], Error>({
    queryKey: ['locations'],
    queryFn: () => listLocations(),
    refetchInterval: (q) => {
      const data = q.state.data;
      if (!data) return false;
      const hasPending = data.some(
        (loc) => loc.import_status === 'pending' || loc.import_status === 'in_progress',
      );
      return hasPending ? POLL_INTERVAL_MS : false;
    },
  });

  const createMutation = useMutation({
    mutationFn: createLocation,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['locations'] });
      closeForm();
    },
    onError: (error) => setFormError(getErrorMessage(error)),
  });

  const updateMutation = useMutation({
    mutationFn: (vars: { id: number; input: LocationCreateInput }) =>
      updateLocation(vars.id, vars.input),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['locations'] });
      closeForm();
    },
    onError: (error) => setFormError(getErrorMessage(error)),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteLocation(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['locations'] });
      setDeleteTarget(null);
    },
  });

  const isSubmitting = createMutation.isPending || updateMutation.isPending;

  const sorted = useMemo(() => {
    if (!query.data) return [];
    return [...query.data].sort((a, b) => a.name.localeCompare(b.name, 'ru'));
  }, [query.data]);

  function openCreate() {
    setEditing(null);
    setForm(EMPTY_FORM);
    setFormError(null);
    setFormOpen(true);
  }

  function openEdit(location: Location) {
    setEditing(location);
    setForm(toFormState(location));
    setFormError(null);
    setFormOpen(true);
  }

  function closeForm() {
    setFormOpen(false);
    setFormError(null);
    setEditing(null);
    setForm(EMPTY_FORM);
  }

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const parsed = parseFormState(form);
    if (typeof parsed === 'string') {
      setFormError(parsed);
      return;
    }
    setFormError(null);
    if (editing) {
      updateMutation.mutate({ id: editing.id, input: parsed });
    } else {
      createMutation.mutate(parsed);
    }
  }

  return (
    <div className="flex h-full flex-col gap-6 p-6 md:p-8">
      <header className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Локации</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Управление локациями и загрузкой исторических данных.
          </p>
        </div>
        <Button onClick={openCreate}>
          <Plus className="h-4 w-4" />
          Добавить локацию
        </Button>
      </header>

      <div className="rounded-md border bg-card">
        {query.isLoading ? (
          <LoadingState />
        ) : query.isError ? (
          <ErrorState
            message={getErrorMessage(query.error)}
            onRetry={() => void query.refetch()}
          />
        ) : sorted.length === 0 ? (
          <EmptyState onCreate={openCreate} />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Название</TableHead>
                <TableHead>Координаты</TableHead>
                <TableHead>Регион</TableHead>
                <TableHead>Тип</TableHead>
                <TableHead className="w-[260px]">Импорт истории</TableHead>
                <TableHead className="w-[140px] text-right">Действия</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {sorted.map((location) => (
                <TableRow
                  key={location.id}
                  className="cursor-pointer"
                  onClick={() => openEdit(location)}
                >
                  <TableCell className="font-medium">{location.name}</TableCell>
                  <TableCell className="font-mono text-xs">
                    {location.latitude.toFixed(4)},{' '}
                    {location.longitude.toFixed(4)}
                  </TableCell>
                  <TableCell>{location.region ?? '—'}</TableCell>
                  <TableCell>{TYPE_LABEL[location.type]}</TableCell>
                  <TableCell>
                    <ImportProgressCell location={location} />
                  </TableCell>
                  <TableCell
                    className="text-right"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => openEdit(location)}
                    >
                      Изменить
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setDeleteTarget(location)}
                    >
                      Удалить
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </div>

      <Dialog
        open={formOpen}
        onOpenChange={(open) => (open ? setFormOpen(true) : closeForm())}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {editing ? 'Редактирование локации' : 'Новая локация'}
            </DialogTitle>
            <DialogDescription>
              {editing
                ? 'Изменения будут сохранены немедленно.'
                : 'После создания запустится загрузка истории за 10 лет.'}
            </DialogDescription>
          </DialogHeader>
          <form
            id="location-form"
            className="grid gap-4"
            onSubmit={handleSubmit}
          >
            <div className="grid gap-2">
              <Label htmlFor="loc-name">Название</Label>
              <Input
                id="loc-name"
                value={form.name}
                onChange={(e) =>
                  setForm((prev) => ({ ...prev, name: e.target.value }))
                }
                required
                maxLength={200}
              />
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="grid gap-2">
                <Label htmlFor="loc-lat">Широта</Label>
                <Input
                  id="loc-lat"
                  type="number"
                  step="0.0001"
                  inputMode="decimal"
                  value={form.latitude}
                  onChange={(e) =>
                    setForm((prev) => ({ ...prev, latitude: e.target.value }))
                  }
                  required
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="loc-lon">Долгота</Label>
                <Input
                  id="loc-lon"
                  type="number"
                  step="0.0001"
                  inputMode="decimal"
                  value={form.longitude}
                  onChange={(e) =>
                    setForm((prev) => ({ ...prev, longitude: e.target.value }))
                  }
                  required
                />
              </div>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="grid gap-2">
                <Label htmlFor="loc-region">Регион</Label>
                <Input
                  id="loc-region"
                  value={form.region}
                  onChange={(e) =>
                    setForm((prev) => ({ ...prev, region: e.target.value }))
                  }
                  maxLength={100}
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="loc-type">Тип</Label>
                <Select
                  value={form.type}
                  onValueChange={(value) =>
                    setForm((prev) => ({
                      ...prev,
                      type: value as LocationType,
                    }))
                  }
                >
                  <SelectTrigger id="loc-type">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="own">Своя</SelectItem>
                    <SelectItem value="purchase">Закупка</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="loc-note">Заметка</Label>
              <Textarea
                id="loc-note"
                value={form.note}
                onChange={(e) =>
                  setForm((prev) => ({ ...prev, note: e.target.value }))
                }
                rows={3}
              />
            </div>
            {formError && (
              <p className="text-sm text-destructive" role="alert">
                {formError}
              </p>
            )}
          </form>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={closeForm}>
              Отмена
            </Button>
            <Button
              type="submit"
              form="location-form"
              disabled={isSubmitting}
            >
              {isSubmitting
                ? 'Сохранение…'
                : editing
                  ? 'Сохранить'
                  : 'Создать'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <AlertDialog
        open={deleteTarget !== null}
        onOpenChange={(open) => {
          if (!open) setDeleteTarget(null);
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Удалить локацию?</AlertDialogTitle>
            <AlertDialogDescription>
              Локация «{deleteTarget?.name}» и связанные с ней данные будут
              удалены без возможности восстановления.
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

function ImportProgressCell({ location }: { location: Location }) {
  const status = location.import_status;
  const label = STATUS_LABEL[status];
  if (status === 'in_progress' || status === 'pending') {
    return (
      <div className="flex flex-col gap-1">
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>{label}</span>
          <span>{location.import_progress}%</span>
        </div>
        <Progress value={location.import_progress} />
      </div>
    );
  }
  if (status === 'error') {
    return <span className="text-sm text-destructive">{label}</span>;
  }
  return <span className="text-sm text-muted-foreground">{label}</span>;
}

function LoadingState() {
  return (
    <div className="flex flex-col gap-3 p-6">
      <div className="h-4 w-1/3 animate-pulse rounded bg-muted" />
      <div className="h-12 w-full animate-pulse rounded bg-muted" />
      <div className="h-12 w-full animate-pulse rounded bg-muted" />
      <div className="h-12 w-full animate-pulse rounded bg-muted" />
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
    <div className="flex flex-col items-center gap-3 p-10 text-center">
      <p className="text-sm text-destructive">{message}</p>
      <Button variant="outline" size="sm" onClick={onRetry}>
        Повторить
      </Button>
    </div>
  );
}

function EmptyState({ onCreate }: { onCreate: () => void }) {
  return (
    <div className="flex flex-col items-center gap-3 p-12 text-center">
      <p className="text-sm text-muted-foreground">
        Локаций пока нет. Добавьте первую, чтобы запустить загрузку истории.
      </p>
      <Button onClick={onCreate}>
        <Plus className="h-4 w-4" />
        Добавить локацию
      </Button>
    </div>
  );
}

export default LocationsPage;
