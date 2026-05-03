import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import axios from 'axios';
import { Plus, Trash2, Upload, X } from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import { type Crop, listCrops } from '@/lib/crops-api';
import {
  type EventType,
  type FieldEvent,
  type FieldEventCreateInput,
  type FieldEventListFilters,
  createEvent,
  deleteEvent,
  deletePhoto,
  getEvent,
  listEvents,
  photoFilename,
  photoSrc,
  updateEvent,
  uploadPhotos,
} from '@/lib/events-api';
import { type Location, listLocations } from '@/lib/locations-api';

const ALL = '__all__';
const MAX_PHOTOS = 5;

const EVENT_TYPE_LABEL: Record<EventType, string> = {
  planting: 'Посадка',
  harvest: 'Сбор',
  note: 'Заметка',
};

const EVENT_TYPES: EventType[] = ['planting', 'harvest', 'note'];

interface FormState {
  location_id: string;
  event_type: EventType;
  event_date: string;
  crop_id: string;
  variety: string;
  area_hectares: string;
  yield_kg: string;
  quality_rating: string;
  description: string;
}

function emptyForm(): FormState {
  return {
    location_id: '',
    event_type: 'planting',
    event_date: new Date().toISOString().slice(0, 10),
    crop_id: '',
    variety: '',
    area_hectares: '',
    yield_kg: '',
    quality_rating: '',
    description: '',
  };
}

function eventToForm(event: FieldEvent): FormState {
  return {
    location_id: String(event.location_id),
    event_type: event.event_type,
    event_date: event.event_date,
    crop_id: event.crop_id === null ? '' : String(event.crop_id),
    variety: event.variety ?? '',
    area_hectares: event.area_hectares === null ? '' : String(event.area_hectares),
    yield_kg: event.yield_kg === null ? '' : String(event.yield_kg),
    quality_rating:
      event.quality_rating === null ? '' : String(event.quality_rating),
    description: event.description ?? '',
  };
}

function parseForm(form: FormState): FieldEventCreateInput | string {
  if (!form.location_id) return 'Выберите локацию';
  const locationId = Number(form.location_id);
  if (!Number.isFinite(locationId)) return 'Неверная локация';
  if (!form.event_date) return 'Укажите дату';

  const cropId = form.crop_id ? Number(form.crop_id) : null;
  const area = form.area_hectares ? Number(form.area_hectares) : null;
  const yieldKg = form.yield_kg ? Number(form.yield_kg) : null;
  const quality = form.quality_rating ? Number(form.quality_rating) : null;

  if (form.event_type === 'planting') {
    if (cropId === null) return 'Для посадки укажите культуру';
  }
  if (form.event_type === 'harvest') {
    if (cropId === null) return 'Для сбора укажите культуру';
    if (yieldKg === null || !Number.isFinite(yieldKg)) {
      return 'Для сбора укажите урожай (кг)';
    }
  }
  if (area !== null && (!Number.isFinite(area) || area <= 0)) {
    return 'Площадь должна быть положительным числом';
  }
  if (yieldKg !== null && (!Number.isFinite(yieldKg) || yieldKg < 0)) {
    return 'Урожай не может быть отрицательным';
  }
  if (
    quality !== null &&
    (!Number.isFinite(quality) || quality < 1 || quality > 5)
  ) {
    return 'Оценка качества — целое число 1..5';
  }

  return {
    location_id: locationId,
    event_type: form.event_type,
    event_date: form.event_date,
    crop_id: cropId,
    variety: form.variety.trim() || null,
    area_hectares: area,
    yield_kg: yieldKg,
    quality_rating: quality,
    description: form.description.trim() || null,
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

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('ru-RU');
}

function isEventType(value: string | null): value is EventType {
  return value === 'planting' || value === 'harvest' || value === 'note';
}

export function EventsPage() {
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();

  const locationParam = searchParams.get('location');
  const typeParam = searchParams.get('type');
  const cropParam = searchParams.get('crop');
  const fromParam = searchParams.get('from') ?? '';
  const toParam = searchParams.get('to') ?? '';

  const filters: FieldEventListFilters = useMemo(() => {
    const out: FieldEventListFilters = {};
    if (locationParam) out.location_id = Number(locationParam);
    if (isEventType(typeParam)) out.event_type = typeParam;
    if (cropParam) out.crop_id = Number(cropParam);
    if (fromParam) out.date_from = fromParam;
    if (toParam) out.date_to = toParam;
    return out;
  }, [locationParam, typeParam, cropParam, fromParam, toParam]);

  function setParam(key: string, value: string | null) {
    const params = new URLSearchParams(searchParams);
    if (value === null || value === '') {
      params.delete(key);
    } else {
      params.set(key, value);
    }
    setSearchParams(params, { replace: true });
  }

  const eventsQuery = useQuery({
    queryKey: ['events', filters],
    queryFn: () => listEvents(filters),
  });

  const locationsQuery = useQuery<Location[], Error>({
    queryKey: ['locations'],
    queryFn: () => listLocations(),
  });

  const cropsQuery = useQuery<Crop[], Error>({
    queryKey: ['crops'],
    queryFn: () => listCrops(),
  });

  const locationName = useMemo(() => {
    const map = new Map<number, string>();
    for (const loc of locationsQuery.data ?? []) map.set(loc.id, loc.name);
    return map;
  }, [locationsQuery.data]);

  const cropName = useMemo(() => {
    const map = new Map<number, string>();
    for (const crop of cropsQuery.data ?? []) map.set(crop.id, crop.name);
    return map;
  }, [cropsQuery.data]);

  const sortedEvents = useMemo(() => {
    if (!eventsQuery.data) return [];
    return [...eventsQuery.data].sort((a, b) =>
      a.event_date < b.event_date ? 1 : a.event_date > b.event_date ? -1 : 0,
    );
  }, [eventsQuery.data]);

  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<FieldEvent | null>(null);
  const [form, setForm] = useState<FormState>(emptyForm());
  const [formError, setFormError] = useState<string | null>(null);
  const [pendingFiles, setPendingFiles] = useState<File[]>([]);

  const [detailId, setDetailId] = useState<number | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<FieldEvent | null>(null);

  const detailQuery = useQuery({
    queryKey: ['event', detailId],
    queryFn: () => {
      if (detailId === null) throw new Error('no id');
      return getEvent(detailId);
    },
    enabled: detailId !== null,
  });

  const createMutation = useMutation({
    mutationFn: async (input: FieldEventCreateInput) => {
      const created = await createEvent(input);
      if (pendingFiles.length > 0) {
        return uploadPhotos(created.id, pendingFiles);
      }
      return created;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['events'] });
      closeForm();
    },
    onError: (error) => setFormError(getErrorMessage(error)),
  });

  const updateMutation = useMutation({
    mutationFn: async (vars: { id: number; input: FieldEventCreateInput }) => {
      const updated = await updateEvent(vars.id, vars.input);
      if (pendingFiles.length > 0) {
        return uploadPhotos(updated.id, pendingFiles);
      }
      return updated;
    },
    onSuccess: (data) => {
      void queryClient.invalidateQueries({ queryKey: ['events'] });
      void queryClient.invalidateQueries({ queryKey: ['event', data.id] });
      closeForm();
    },
    onError: (error) => setFormError(getErrorMessage(error)),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteEvent(id),
    onSuccess: (_data, id) => {
      void queryClient.invalidateQueries({ queryKey: ['events'] });
      queryClient.removeQueries({ queryKey: ['event', id] });
      setDeleteTarget(null);
      if (detailId === id) setDetailId(null);
    },
  });

  const deletePhotoMutation = useMutation({
    mutationFn: (vars: { id: number; filename: string }) =>
      deletePhoto(vars.id, vars.filename),
    onSuccess: (data) => {
      void queryClient.invalidateQueries({ queryKey: ['events'] });
      void queryClient.invalidateQueries({ queryKey: ['event', data.id] });
    },
  });

  const uploadPhotosMutation = useMutation({
    mutationFn: (vars: { id: number; files: File[] }) =>
      uploadPhotos(vars.id, vars.files),
    onSuccess: (data) => {
      void queryClient.invalidateQueries({ queryKey: ['events'] });
      void queryClient.invalidateQueries({ queryKey: ['event', data.id] });
    },
  });

  function openCreate() {
    setEditing(null);
    setForm(emptyForm());
    setPendingFiles([]);
    setFormError(null);
    setFormOpen(true);
  }

  function openEdit(event: FieldEvent) {
    setEditing(event);
    setForm(eventToForm(event));
    setPendingFiles([]);
    setFormError(null);
    setFormOpen(true);
  }

  function closeForm() {
    setFormOpen(false);
    setEditing(null);
    setForm(emptyForm());
    setPendingFiles([]);
    setFormError(null);
  }

  function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const parsed = parseForm(form);
    if (typeof parsed === 'string') {
      setFormError(parsed);
      return;
    }
    const existingPhotos = editing ? editing.photos.length : 0;
    if (existingPhotos + pendingFiles.length > MAX_PHOTOS) {
      setFormError(`Максимум ${MAX_PHOTOS} фото`);
      return;
    }
    setFormError(null);
    if (editing) {
      updateMutation.mutate({ id: editing.id, input: parsed });
    } else {
      createMutation.mutate(parsed);
    }
  }

  const isSubmitting = createMutation.isPending || updateMutation.isPending;

  const detailEvent = detailQuery.data;

  return (
    <div className="flex h-full flex-col gap-6 p-4 sm:p-6 md:p-8">
      <header className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-col gap-1">
          <h1 className="text-2xl font-semibold tracking-tight">События</h1>
          <p className="text-sm text-muted-foreground">
            Журнал полевых работ: посадки, сборы, заметки.
          </p>
        </div>
        <Button onClick={openCreate}>
          <Plus className="h-4 w-4" />
          Добавить событие
        </Button>
      </header>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <div className="grid gap-1.5">
          <Label htmlFor="ev-location">Локация</Label>
          <Select
            value={locationParam ?? ALL}
            onValueChange={(v) => setParam('location', v === ALL ? null : v)}
          >
            <SelectTrigger id="ev-location">
              <SelectValue placeholder="Все" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>Все</SelectItem>
              {locationsQuery.data?.map((loc) => (
                <SelectItem key={loc.id} value={String(loc.id)}>
                  {loc.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="ev-type">Тип</Label>
          <Select
            value={typeParam ?? ALL}
            onValueChange={(v) => setParam('type', v === ALL ? null : v)}
          >
            <SelectTrigger id="ev-type">
              <SelectValue placeholder="Все" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>Все</SelectItem>
              {EVENT_TYPES.map((t) => (
                <SelectItem key={t} value={t}>
                  {EVENT_TYPE_LABEL[t]}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="ev-crop">Культура</Label>
          <Select
            value={cropParam ?? ALL}
            onValueChange={(v) => setParam('crop', v === ALL ? null : v)}
          >
            <SelectTrigger id="ev-crop">
              <SelectValue placeholder="Все" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>Все</SelectItem>
              {cropsQuery.data?.map((c) => (
                <SelectItem key={c.id} value={String(c.id)}>
                  {c.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="ev-from">С даты</Label>
          <Input
            id="ev-from"
            type="date"
            value={fromParam}
            onChange={(e) => setParam('from', e.target.value || null)}
          />
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="ev-to">По дату</Label>
          <Input
            id="ev-to"
            type="date"
            value={toParam}
            onChange={(e) => setParam('to', e.target.value || null)}
          />
        </div>
      </div>

      <div className="flex flex-col gap-3">
        {eventsQuery.isLoading ? (
          <LoadingState />
        ) : eventsQuery.isError ? (
          <ErrorState
            message={getErrorMessage(eventsQuery.error)}
            onRetry={() => void eventsQuery.refetch()}
          />
        ) : sortedEvents.length === 0 ? (
          <EmptyState message="Событий не найдено. Создайте первое или измените фильтры." />
        ) : (
          sortedEvents.map((event) => (
            <Card
              key={event.id}
              className="cursor-pointer transition-shadow hover:shadow"
              onClick={() => setDetailId(event.id)}
            >
              <CardHeader className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                <div className="flex flex-col gap-1">
                  <CardTitle className="text-base">
                    {EVENT_TYPE_LABEL[event.event_type]}
                    {event.crop_id !== null
                      ? ` · ${cropName.get(event.crop_id) ?? `#${event.crop_id}`}`
                      : ''}
                  </CardTitle>
                  <CardDescription>
                    {formatDate(event.event_date)} ·{' '}
                    {locationName.get(event.location_id) ??
                      `Локация #${event.location_id}`}
                  </CardDescription>
                </div>
                <div className="flex gap-2">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={(e) => {
                      e.stopPropagation();
                      openEdit(event);
                    }}
                  >
                    Изменить
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={(e) => {
                      e.stopPropagation();
                      setDeleteTarget(event);
                    }}
                  >
                    Удалить
                  </Button>
                </div>
              </CardHeader>
              {(event.description ||
                event.area_hectares !== null ||
                event.yield_kg !== null ||
                event.photos.length > 0) && (
                <CardContent className="flex flex-col gap-2 text-sm">
                  {event.description && (
                    <p className="line-clamp-2 text-muted-foreground">
                      {event.description}
                    </p>
                  )}
                  <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
                    {event.area_hectares !== null && (
                      <span>Площадь: {event.area_hectares} га</span>
                    )}
                    {event.yield_kg !== null && (
                      <span>Урожай: {event.yield_kg} кг</span>
                    )}
                    {event.variety && <span>Сорт: {event.variety}</span>}
                    {event.quality_rating !== null && (
                      <span>Качество: {event.quality_rating}/5</span>
                    )}
                    {event.photos.length > 0 && (
                      <span>Фото: {event.photos.length}</span>
                    )}
                  </div>
                </CardContent>
              )}
            </Card>
          ))
        )}
      </div>

      <Dialog
        open={formOpen}
        onOpenChange={(open) => (open ? setFormOpen(true) : closeForm())}
      >
        <DialogContent className="max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>
              {editing ? 'Редактирование события' : 'Новое событие'}
            </DialogTitle>
            <DialogDescription>
              Заполните поля в зависимости от типа события.
            </DialogDescription>
          </DialogHeader>
          <form
            id="event-form"
            className="grid gap-4"
            onSubmit={handleSubmit}
          >
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="grid gap-2">
                <Label htmlFor="ev-form-type">Тип</Label>
                <Select
                  value={form.event_type}
                  onValueChange={(v) =>
                    setForm((p) => ({ ...p, event_type: v as EventType }))
                  }
                >
                  <SelectTrigger id="ev-form-type">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {EVENT_TYPES.map((t) => (
                      <SelectItem key={t} value={t}>
                        {EVENT_TYPE_LABEL[t]}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="grid gap-2">
                <Label htmlFor="ev-form-date">Дата</Label>
                <Input
                  id="ev-form-date"
                  type="date"
                  value={form.event_date}
                  onChange={(e) =>
                    setForm((p) => ({ ...p, event_date: e.target.value }))
                  }
                  required
                />
              </div>
            </div>

            <div className="grid gap-2">
              <Label htmlFor="ev-form-location">Локация</Label>
              <Select
                value={form.location_id || ''}
                onValueChange={(v) =>
                  setForm((p) => ({ ...p, location_id: v }))
                }
              >
                <SelectTrigger id="ev-form-location">
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

            {(form.event_type === 'planting' ||
              form.event_type === 'harvest') && (
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="grid gap-2">
                  <Label htmlFor="ev-form-crop">Культура</Label>
                  <Select
                    value={form.crop_id || ''}
                    onValueChange={(v) =>
                      setForm((p) => ({ ...p, crop_id: v }))
                    }
                  >
                    <SelectTrigger id="ev-form-crop">
                      <SelectValue placeholder="Выберите культуру" />
                    </SelectTrigger>
                    <SelectContent>
                      {cropsQuery.data?.map((c) => (
                        <SelectItem key={c.id} value={String(c.id)}>
                          {c.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="ev-form-variety">Сорт</Label>
                  <Input
                    id="ev-form-variety"
                    value={form.variety}
                    maxLength={100}
                    onChange={(e) =>
                      setForm((p) => ({ ...p, variety: e.target.value }))
                    }
                  />
                </div>
              </div>
            )}

            {form.event_type === 'planting' && (
              <div className="grid gap-2">
                <Label htmlFor="ev-form-area">Площадь, га</Label>
                <Input
                  id="ev-form-area"
                  type="number"
                  step="any"
                  min="0"
                  inputMode="decimal"
                  value={form.area_hectares}
                  onChange={(e) =>
                    setForm((p) => ({ ...p, area_hectares: e.target.value }))
                  }
                />
              </div>
            )}

            {form.event_type === 'harvest' && (
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="grid gap-2">
                  <Label htmlFor="ev-form-yield">Урожай, кг</Label>
                  <Input
                    id="ev-form-yield"
                    type="number"
                    step="any"
                    min="0"
                    inputMode="decimal"
                    value={form.yield_kg}
                    onChange={(e) =>
                      setForm((p) => ({ ...p, yield_kg: e.target.value }))
                    }
                    required
                  />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="ev-form-quality">Качество (1–5)</Label>
                  <Input
                    id="ev-form-quality"
                    type="number"
                    step="1"
                    min="1"
                    max="5"
                    inputMode="numeric"
                    value={form.quality_rating}
                    onChange={(e) =>
                      setForm((p) => ({ ...p, quality_rating: e.target.value }))
                    }
                  />
                </div>
              </div>
            )}

            <div className="grid gap-2">
              <Label htmlFor="ev-form-desc">Описание</Label>
              <Textarea
                id="ev-form-desc"
                value={form.description}
                onChange={(e) =>
                  setForm((p) => ({ ...p, description: e.target.value }))
                }
                rows={4}
              />
            </div>

            <PhotoPicker
              files={pendingFiles}
              setFiles={setPendingFiles}
              existingCount={editing ? editing.photos.length : 0}
            />

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
            <Button type="submit" form="event-form" disabled={isSubmitting}>
              {isSubmitting
                ? 'Сохранение…'
                : editing
                  ? 'Сохранить'
                  : 'Создать'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={detailId !== null}
        onOpenChange={(open) => {
          if (!open) setDetailId(null);
        }}
      >
        <DialogContent className="max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Событие</DialogTitle>
            <DialogDescription>
              Данные, погода в этот день и фотографии.
            </DialogDescription>
          </DialogHeader>
          {detailQuery.isLoading ? (
            <LoadingState />
          ) : detailQuery.isError ? (
            <ErrorState
              message={getErrorMessage(detailQuery.error)}
              onRetry={() => void detailQuery.refetch()}
            />
          ) : detailEvent ? (
            <EventDetail
              event={detailEvent}
              locationName={
                locationName.get(detailEvent.location_id) ??
                `Локация #${detailEvent.location_id}`
              }
              cropName={
                detailEvent.crop_id !== null
                  ? (cropName.get(detailEvent.crop_id) ??
                    `#${detailEvent.crop_id}`)
                  : null
              }
              onUploadPhotos={(files) =>
                uploadPhotosMutation.mutate({ id: detailEvent.id, files })
              }
              isUploading={uploadPhotosMutation.isPending}
              uploadError={
                uploadPhotosMutation.isError
                  ? getErrorMessage(uploadPhotosMutation.error)
                  : null
              }
              onDeletePhoto={(filename) =>
                deletePhotoMutation.mutate({
                  id: detailEvent.id,
                  filename,
                })
              }
              isDeletingPhoto={deletePhotoMutation.isPending}
            />
          ) : null}
          <DialogFooter>
            {detailEvent && (
              <>
                <Button
                  variant="outline"
                  onClick={() => {
                    setDeleteTarget(detailEvent);
                  }}
                >
                  Удалить
                </Button>
                <Button
                  onClick={() => {
                    openEdit(detailEvent);
                    setDetailId(null);
                  }}
                >
                  Изменить
                </Button>
              </>
            )}
            <Button variant="outline" onClick={() => setDetailId(null)}>
              Закрыть
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
            <AlertDialogTitle>Удалить событие?</AlertDialogTitle>
            <AlertDialogDescription>
              Событие «{deleteTarget && EVENT_TYPE_LABEL[deleteTarget.event_type]}»
              от{' '}
              {deleteTarget && formatDate(deleteTarget.event_date)} будет
              удалено вместе с фотографиями.
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

function EventDetail({
  event,
  locationName,
  cropName,
  onUploadPhotos,
  isUploading,
  uploadError,
  onDeletePhoto,
  isDeletingPhoto,
}: {
  event: FieldEvent;
  locationName: string;
  cropName: string | null;
  onUploadPhotos: (files: File[]) => void;
  isUploading: boolean;
  uploadError: string | null;
  onDeletePhoto: (filename: string) => void;
  isDeletingPhoto: boolean;
}) {
  const remaining = MAX_PHOTOS - event.photos.length;

  return (
    <div className="grid gap-4">
      <section className="grid gap-2 text-sm">
        <div className="grid grid-cols-1 gap-1 sm:grid-cols-2">
          <DetailRow label="Тип" value={EVENT_TYPE_LABEL[event.event_type]} />
          <DetailRow label="Дата" value={formatDate(event.event_date)} />
          <DetailRow label="Локация" value={locationName} />
          {cropName && <DetailRow label="Культура" value={cropName} />}
          {event.variety && (
            <DetailRow label="Сорт" value={event.variety} />
          )}
          {event.area_hectares !== null && (
            <DetailRow label="Площадь" value={`${event.area_hectares} га`} />
          )}
          {event.yield_kg !== null && (
            <DetailRow label="Урожай" value={`${event.yield_kg} кг`} />
          )}
          {event.quality_rating !== null && (
            <DetailRow
              label="Качество"
              value={`${event.quality_rating}/5`}
            />
          )}
        </div>
        {event.description && (
          <div className="rounded-md border bg-muted/40 p-3">
            <p className="whitespace-pre-wrap text-sm">{event.description}</p>
          </div>
        )}
      </section>

      <section className="grid gap-2">
        <h3 className="text-sm font-semibold">Погода в этот день</h3>
        {event.weather === null ? (
          <p className="text-sm text-muted-foreground">
            Данных о погоде за эту дату нет.
          </p>
        ) : (
          <div className="grid grid-cols-2 gap-2 text-xs sm:grid-cols-3">
            <WeatherCell
              label="Темп. мин"
              value={event.weather.temp_min}
              unit="°C"
            />
            <WeatherCell
              label="Темп. макс"
              value={event.weather.temp_max}
              unit="°C"
            />
            <WeatherCell
              label="Темп. ср"
              value={event.weather.temp_avg}
              unit="°C"
            />
            <WeatherCell
              label="Осадки"
              value={event.weather.precipitation}
              unit="мм"
            />
            <WeatherCell
              label="Влажн. ср"
              value={event.weather.humidity_avg}
              unit="%"
            />
            <WeatherCell
              label="Ветер ср"
              value={event.weather.wind_speed_avg}
              unit="м/с"
            />
            <WeatherCell
              label="Точка росы"
              value={event.weather.dew_point}
              unit="°C"
            />
            <WeatherCell label="VPD" value={event.weather.vpd} unit="кПа" />
            <WeatherCell
              label="Заморозки"
              value={event.weather.frost_hours}
              unit="ч"
            />
          </div>
        )}
      </section>

      <section className="grid gap-2">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold">
            Фото ({event.photos.length}/{MAX_PHOTOS})
          </h3>
          {remaining > 0 && (
            <PhotoUploadButton
              remaining={remaining}
              disabled={isUploading}
              onFiles={onUploadPhotos}
            />
          )}
        </div>
        {uploadError && (
          <p className="text-xs text-destructive" role="alert">
            {uploadError}
          </p>
        )}
        {event.photos.length === 0 ? (
          <p className="text-sm text-muted-foreground">Фотографий нет.</p>
        ) : (
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            {event.photos.map((path) => {
              const filename = photoFilename(path);
              return (
                <div
                  key={path}
                  className="relative overflow-hidden rounded-md border"
                >
                  <img
                    src={photoSrc(path)}
                    alt={filename}
                    className="aspect-square w-full object-cover"
                  />
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="absolute right-1 top-1 h-7 w-7 p-0"
                    disabled={isDeletingPhoto}
                    onClick={() => onDeletePhoto(filename)}
                    aria-label="Удалить фото"
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
}

function PhotoUploadButton({
  remaining,
  disabled,
  onFiles,
}: {
  remaining: number;
  disabled: boolean;
  onFiles: (files: File[]) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);

  return (
    <>
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        multiple
        className="hidden"
        onChange={(e) => {
          const list = e.target.files;
          if (!list || list.length === 0) return;
          const files = Array.from(list).slice(0, remaining);
          onFiles(files);
          e.target.value = '';
        }}
      />
      <Button
        type="button"
        variant="outline"
        size="sm"
        disabled={disabled}
        onClick={() => inputRef.current?.click()}
      >
        <Upload className="h-4 w-4" />
        Загрузить
      </Button>
    </>
  );
}

function PhotoPicker({
  files,
  setFiles,
  existingCount,
}: {
  files: File[];
  setFiles: React.Dispatch<React.SetStateAction<File[]>>;
  existingCount: number;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);
  const [previews, setPreviews] = useState<string[]>([]);

  useEffect(() => {
    const urls = files.map((f) => URL.createObjectURL(f));
    setPreviews(urls);
    return () => {
      for (const u of urls) URL.revokeObjectURL(u);
    };
  }, [files]);

  const remaining = MAX_PHOTOS - existingCount - files.length;

  function addFiles(list: FileList | File[]) {
    const incoming = Array.from(list).filter((f) =>
      f.type.startsWith('image/'),
    );
    if (incoming.length === 0) return;
    setFiles((prev) => {
      const room = MAX_PHOTOS - existingCount - prev.length;
      if (room <= 0) return prev;
      return [...prev, ...incoming.slice(0, room)];
    });
  }

  function handleDrop(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer.files.length > 0) {
      addFiles(e.dataTransfer.files);
    }
  }

  return (
    <div className="grid gap-2">
      <div className="flex items-center justify-between">
        <Label>Фото (до {MAX_PHOTOS})</Label>
        <span className="text-xs text-muted-foreground">
          {existingCount + files.length}/{MAX_PHOTOS}
        </span>
      </div>
      <div
        className={`flex flex-col items-center justify-center gap-2 rounded-md border border-dashed p-4 text-center text-sm ${
          dragOver ? 'border-primary bg-muted/40' : 'border-input'
        }`}
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
      >
        <p className="text-muted-foreground">
          Перетащите файлы или выберите вручную.
        </p>
        <input
          ref={inputRef}
          type="file"
          accept="image/*"
          multiple
          className="hidden"
          onChange={(e) => {
            if (e.target.files) addFiles(e.target.files);
            e.target.value = '';
          }}
        />
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={remaining <= 0}
          onClick={() => inputRef.current?.click()}
        >
          <Upload className="h-4 w-4" />
          Выбрать файлы
        </Button>
      </div>
      {files.length > 0 && (
        <div className="grid grid-cols-3 gap-2 sm:grid-cols-5">
          {files.map((file, idx) => (
            <div
              key={`${file.name}-${idx}`}
              className="relative overflow-hidden rounded-md border"
            >
              <img
                src={previews[idx]}
                alt={file.name}
                className="aspect-square w-full object-cover"
              />
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="absolute right-1 top-1 h-6 w-6 p-0"
                onClick={() =>
                  setFiles((prev) => prev.filter((_, i) => i !== idx))
                }
                aria-label="Убрать"
              >
                <X className="h-3 w-3" />
              </Button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-0.5 rounded-md border p-2">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className="text-sm">{value}</span>
    </div>
  );
}

function WeatherCell({
  label,
  value,
  unit,
}: {
  label: string;
  value: number | null;
  unit: string;
}) {
  return (
    <div className="flex flex-col gap-0.5 rounded-md border p-2">
      <span className="text-[10px] uppercase text-muted-foreground">
        {label}
      </span>
      <span className="font-mono text-sm">
        {value === null ? '—' : `${value.toFixed(1)} ${unit}`}
      </span>
    </div>
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

export default EventsPage;
