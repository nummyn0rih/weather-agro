import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import axios from 'axios';
import { Plus } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  type AlertCondition,
  type AlertHistoryFilters,
  type AlertParameter,
  type AlertRule,
  type AlertRuleCreateInput,
  createRule,
  deleteRule,
  getTelegramStatus,
  issueTelegramBindCode,
  listHistory,
  listRules,
  unbindTelegram,
  updateRule,
} from '@/lib/alerts-api';
import { type Location, listLocations } from '@/lib/locations-api';

type TabKey = 'rules' | 'history';

const PARAMETER_OPTIONS: { value: AlertParameter; label: string }[] = [
  { value: 'temperature_avg', label: 'Температура (средняя)' },
  { value: 'temperature_min', label: 'Температура (мин)' },
  { value: 'temperature_max', label: 'Температура (макс)' },
  { value: 'precipitation', label: 'Осадки' },
  { value: 'humidity_avg', label: 'Влажность' },
  { value: 'wind_speed_avg', label: 'Ветер (средний)' },
  { value: 'wind_speed_max', label: 'Ветер (макс)' },
  { value: 'pressure_avg', label: 'Давление' },
  { value: 'vpd_avg', label: 'VPD' },
  { value: 'soil_moisture_avg', label: 'Влажность почвы' },
  { value: 'soil_temperature_avg', label: 'Температура почвы' },
];

const PARAMETER_LABEL: Record<string, string> = Object.fromEntries(
  PARAMETER_OPTIONS.map((o) => [o.value, o.label]),
);

const CONDITION_OPTIONS: { value: AlertCondition; label: string }[] = [
  { value: 'gt', label: 'больше (>)' },
  { value: 'lt', label: 'меньше (<)' },
  { value: 'eq', label: 'равно (=)' },
  { value: 'between', label: 'между' },
];

const CONDITION_LABEL: Record<string, string> = Object.fromEntries(
  CONDITION_OPTIONS.map((o) => [o.value, o.label]),
);

interface Template {
  key: string;
  label: string;
  preset: AlertRuleCreateInput;
}

const TEMPLATES: Template[] = [
  {
    key: 'heat',
    label: 'Жара',
    preset: {
      name: 'Жара',
      parameter: 'temperature_max',
      condition: 'gt',
      threshold: 30,
      threshold_max: null,
      location_ids: [],
      enabled: true,
      telegram: true,
    },
  },
  {
    key: 'frost',
    label: 'Заморозки',
    preset: {
      name: 'Заморозки',
      parameter: 'temperature_min',
      condition: 'lt',
      threshold: 0,
      threshold_max: null,
      location_ids: [],
      enabled: true,
      telegram: true,
    },
  },
  {
    key: 'storm',
    label: 'Ливень',
    preset: {
      name: 'Ливень',
      parameter: 'precipitation',
      condition: 'gt',
      threshold: 20,
      threshold_max: null,
      location_ids: [],
      enabled: true,
      telegram: true,
    },
  },
];

interface FormState {
  name: string;
  parameter: AlertParameter;
  condition: AlertCondition;
  threshold: string;
  threshold_max: string;
  location_ids: number[];
  enabled: boolean;
  telegram: boolean;
}

const EMPTY_FORM: FormState = {
  name: '',
  parameter: 'temperature_max',
  condition: 'gt',
  threshold: '',
  threshold_max: '',
  location_ids: [],
  enabled: true,
  telegram: true,
};

function ruleToFormState(rule: AlertRule): FormState {
  return {
    name: rule.name,
    parameter: rule.parameter,
    condition: rule.condition,
    threshold: String(rule.threshold),
    threshold_max:
      rule.threshold_max === null ? '' : String(rule.threshold_max),
    location_ids: rule.location_ids,
    enabled: rule.enabled,
    telegram: rule.telegram,
  };
}

function presetToFormState(preset: AlertRuleCreateInput): FormState {
  return {
    name: preset.name,
    parameter: preset.parameter,
    condition: preset.condition,
    threshold: String(preset.threshold),
    threshold_max:
      preset.threshold_max === null ? '' : String(preset.threshold_max),
    location_ids: preset.location_ids,
    enabled: preset.enabled,
    telegram: preset.telegram,
  };
}

function parseFormState(form: FormState): AlertRuleCreateInput | string {
  const name = form.name.trim();
  if (name.length === 0) return 'Укажите название';
  const threshold = Number(form.threshold);
  if (!Number.isFinite(threshold)) return 'Порог должен быть числом';
  let thresholdMax: number | null = null;
  if (form.condition === 'between') {
    thresholdMax = Number(form.threshold_max);
    if (!Number.isFinite(thresholdMax)) {
      return 'Верхняя граница должна быть числом';
    }
    if (thresholdMax <= threshold) {
      return 'Верхняя граница должна быть больше нижней';
    }
  }
  return {
    name,
    parameter: form.parameter,
    condition: form.condition,
    threshold,
    threshold_max: thresholdMax,
    location_ids: form.location_ids,
    enabled: form.enabled,
    telegram: form.telegram,
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

function formatTriggeredAt(iso: string): string {
  return new Date(iso).toLocaleString('ru-RU');
}

function formatCondition(
  condition: string,
  threshold: number,
  thresholdMax: number | null,
): string {
  if (condition === 'between' && thresholdMax !== null) {
    return `${threshold} – ${thresholdMax}`;
  }
  if (condition === 'gt') return `> ${threshold}`;
  if (condition === 'lt') return `< ${threshold}`;
  if (condition === 'eq') return `= ${threshold}`;
  return `${condition} ${threshold}`;
}

function isTabKey(value: string | null): value is TabKey {
  return value === 'rules' || value === 'history';
}

export function AlertsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const tabParam = searchParams.get('tab');
  const tab: TabKey = isTabKey(tabParam) ? tabParam : 'rules';

  function setTab(next: TabKey) {
    const params = new URLSearchParams(searchParams);
    params.set('tab', next);
    setSearchParams(params, { replace: true });
  }

  return (
    <div className="flex h-full flex-col gap-6 p-6 md:p-8">
      <header className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold tracking-tight">Алерты</h1>
        <p className="text-sm text-muted-foreground">
          Правила оповещений и история срабатываний.
        </p>
      </header>

      <div className="flex gap-2 border-b">
        <Button
          variant={tab === 'rules' ? 'default' : 'ghost'}
          size="sm"
          onClick={() => setTab('rules')}
        >
          Правила
        </Button>
        <Button
          variant={tab === 'history' ? 'default' : 'ghost'}
          size="sm"
          onClick={() => setTab('history')}
        >
          История срабатываний
        </Button>
      </div>

      {tab === 'rules' ? <RulesTab /> : <HistoryTab />}
    </div>
  );
}

function RulesTab() {
  const queryClient = useQueryClient();
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<AlertRule | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [formError, setFormError] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<AlertRule | null>(null);
  const [telegramOpen, setTelegramOpen] = useState(false);

  const rulesQuery = useQuery<AlertRule[], Error>({
    queryKey: ['alerts', 'rules'],
    queryFn: () => listRules(),
  });

  const locationsQuery = useQuery<Location[], Error>({
    queryKey: ['locations'],
    queryFn: () => listLocations(),
  });

  const createMutation = useMutation({
    mutationFn: createRule,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['alerts', 'rules'] });
      closeForm();
    },
    onError: (error) => setFormError(getErrorMessage(error)),
  });

  const updateMutation = useMutation({
    mutationFn: (vars: { id: number; input: AlertRuleCreateInput }) =>
      updateRule(vars.id, vars.input),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['alerts', 'rules'] });
      closeForm();
    },
    onError: (error) => setFormError(getErrorMessage(error)),
  });

  const toggleMutation = useMutation({
    mutationFn: (vars: { id: number; enabled: boolean }) =>
      updateRule(vars.id, { enabled: vars.enabled }),
    onSuccess: () =>
      void queryClient.invalidateQueries({ queryKey: ['alerts', 'rules'] }),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteRule(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['alerts', 'rules'] });
      setDeleteTarget(null);
    },
  });

  const isSubmitting = createMutation.isPending || updateMutation.isPending;
  const sortedRules = useMemo(() => {
    if (!rulesQuery.data) return [];
    return [...rulesQuery.data].sort((a, b) => a.name.localeCompare(b.name, 'ru'));
  }, [rulesQuery.data]);

  function openCreate() {
    setEditing(null);
    setForm(EMPTY_FORM);
    setFormError(null);
    setFormOpen(true);
  }

  function openEdit(rule: AlertRule) {
    setEditing(rule);
    setForm(ruleToFormState(rule));
    setFormError(null);
    setFormOpen(true);
  }

  function applyTemplate(template: Template) {
    setEditing(null);
    setForm(presetToFormState(template.preset));
    setFormError(null);
    setFormOpen(true);
  }

  function closeForm() {
    setFormOpen(false);
    setEditing(null);
    setForm(EMPTY_FORM);
    setFormError(null);
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

  function toggleLocation(id: number) {
    setForm((prev) => {
      const exists = prev.location_ids.includes(id);
      return {
        ...prev,
        location_ids: exists
          ? prev.location_ids.filter((x) => x !== id)
          : [...prev.location_ids, id],
      };
    });
  }

  return (
    <>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-wrap gap-2">
          <span className="text-sm text-muted-foreground self-center">
            Шаблоны:
          </span>
          {TEMPLATES.map((tpl) => (
            <Button
              key={tpl.key}
              variant="outline"
              size="sm"
              onClick={() => applyTemplate(tpl)}
            >
              {tpl.label}
            </Button>
          ))}
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => setTelegramOpen(true)}>
            Привязать Telegram
          </Button>
          <Button onClick={openCreate}>
            <Plus className="h-4 w-4" />
            Новое правило
          </Button>
        </div>
      </div>

      <div className="rounded-md border bg-card">
        {rulesQuery.isLoading ? (
          <LoadingState />
        ) : rulesQuery.isError ? (
          <ErrorState
            message={getErrorMessage(rulesQuery.error)}
            onRetry={() => void rulesQuery.refetch()}
          />
        ) : sortedRules.length === 0 ? (
          <EmptyState message="Правил нет. Создайте первое или используйте шаблон." />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-[110px]">Включено</TableHead>
                <TableHead>Название</TableHead>
                <TableHead>Параметр</TableHead>
                <TableHead>Условие</TableHead>
                <TableHead>Локации</TableHead>
                <TableHead>Telegram</TableHead>
                <TableHead className="w-[160px] text-right">Действия</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {sortedRules.map((rule) => (
                <TableRow key={rule.id}>
                  <TableCell>
                    <Button
                      variant={rule.enabled ? 'default' : 'outline'}
                      size="sm"
                      disabled={toggleMutation.isPending}
                      onClick={() =>
                        toggleMutation.mutate({
                          id: rule.id,
                          enabled: !rule.enabled,
                        })
                      }
                    >
                      {rule.enabled ? 'Вкл' : 'Выкл'}
                    </Button>
                  </TableCell>
                  <TableCell className="font-medium">{rule.name}</TableCell>
                  <TableCell>
                    {PARAMETER_LABEL[rule.parameter] ?? rule.parameter}
                  </TableCell>
                  <TableCell className="font-mono text-xs">
                    {formatCondition(
                      rule.condition,
                      rule.threshold,
                      rule.threshold_max,
                    )}
                  </TableCell>
                  <TableCell>
                    {rule.location_ids.length === 0
                      ? 'Все'
                      : rule.location_ids.length}
                  </TableCell>
                  <TableCell>{rule.telegram ? 'Да' : 'Нет'}</TableCell>
                  <TableCell className="text-right">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => openEdit(rule)}
                    >
                      Изменить
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setDeleteTarget(rule)}
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
              {editing ? 'Редактирование правила' : 'Новое правило'}
            </DialogTitle>
            <DialogDescription>
              Настройте параметр, условие и пороговое значение.
            </DialogDescription>
          </DialogHeader>
          <form
            id="alert-rule-form"
            className="grid gap-4"
            onSubmit={handleSubmit}
          >
            <div className="grid gap-2">
              <Label htmlFor="rule-name">Название</Label>
              <Input
                id="rule-name"
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
                <Label htmlFor="rule-parameter">Параметр</Label>
                <Select
                  value={form.parameter}
                  onValueChange={(value) =>
                    setForm((prev) => ({
                      ...prev,
                      parameter: value as AlertParameter,
                    }))
                  }
                >
                  <SelectTrigger id="rule-parameter">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {PARAMETER_OPTIONS.map((opt) => (
                      <SelectItem key={opt.value} value={opt.value}>
                        {opt.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="grid gap-2">
                <Label htmlFor="rule-condition">Условие</Label>
                <Select
                  value={form.condition}
                  onValueChange={(value) =>
                    setForm((prev) => ({
                      ...prev,
                      condition: value as AlertCondition,
                    }))
                  }
                >
                  <SelectTrigger id="rule-condition">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {CONDITION_OPTIONS.map((opt) => (
                      <SelectItem key={opt.value} value={opt.value}>
                        {opt.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="grid gap-2">
                <Label htmlFor="rule-threshold">
                  {form.condition === 'between' ? 'Нижняя граница' : 'Порог'}
                </Label>
                <Input
                  id="rule-threshold"
                  type="number"
                  step="any"
                  inputMode="decimal"
                  value={form.threshold}
                  onChange={(e) =>
                    setForm((prev) => ({ ...prev, threshold: e.target.value }))
                  }
                  required
                />
              </div>
              {form.condition === 'between' && (
                <div className="grid gap-2">
                  <Label htmlFor="rule-threshold-max">Верхняя граница</Label>
                  <Input
                    id="rule-threshold-max"
                    type="number"
                    step="any"
                    inputMode="decimal"
                    value={form.threshold_max}
                    onChange={(e) =>
                      setForm((prev) => ({
                        ...prev,
                        threshold_max: e.target.value,
                      }))
                    }
                    required
                  />
                </div>
              )}
            </div>
            <div className="grid gap-2">
              <Label>Локации</Label>
              <p className="text-xs text-muted-foreground">
                Не выбрано — правило срабатывает для всех локаций.
              </p>
              <div className="flex flex-wrap gap-2">
                {locationsQuery.data?.map((loc) => {
                  const selected = form.location_ids.includes(loc.id);
                  return (
                    <Button
                      key={loc.id}
                      type="button"
                      variant={selected ? 'default' : 'outline'}
                      size="sm"
                      onClick={() => toggleLocation(loc.id)}
                    >
                      {loc.name}
                    </Button>
                  );
                })}
                {locationsQuery.data && locationsQuery.data.length === 0 && (
                  <span className="text-xs text-muted-foreground">
                    Локаций нет.
                  </span>
                )}
              </div>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="flex items-center justify-between rounded-md border px-3 py-2">
                <Label htmlFor="rule-enabled" className="text-sm">
                  Включено
                </Label>
                <Button
                  id="rule-enabled"
                  type="button"
                  variant={form.enabled ? 'default' : 'outline'}
                  size="sm"
                  onClick={() =>
                    setForm((prev) => ({ ...prev, enabled: !prev.enabled }))
                  }
                >
                  {form.enabled ? 'Да' : 'Нет'}
                </Button>
              </div>
              <div className="flex items-center justify-between rounded-md border px-3 py-2">
                <Label htmlFor="rule-telegram" className="text-sm">
                  Telegram
                </Label>
                <Button
                  id="rule-telegram"
                  type="button"
                  variant={form.telegram ? 'default' : 'outline'}
                  size="sm"
                  onClick={() =>
                    setForm((prev) => ({ ...prev, telegram: !prev.telegram }))
                  }
                >
                  {form.telegram ? 'Да' : 'Нет'}
                </Button>
              </div>
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
              form="alert-rule-form"
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
            <AlertDialogTitle>Удалить правило?</AlertDialogTitle>
            <AlertDialogDescription>
              Правило «{deleteTarget?.name}» будет удалено. История
              срабатываний сохранится.
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

      <TelegramBindDialog
        open={telegramOpen}
        onClose={() => setTelegramOpen(false)}
      />
    </>
  );
}

function HistoryTab() {
  const [searchParams, setSearchParams] = useSearchParams();

  const locationId = searchParams.get('location_id');
  const ruleId = searchParams.get('rule_id');
  const dateFrom = searchParams.get('date_from') ?? '';
  const dateTo = searchParams.get('date_to') ?? '';
  const offset = Number(searchParams.get('offset') ?? '0') || 0;
  const limit = 50;

  function setParam(key: string, value: string | null) {
    const params = new URLSearchParams(searchParams);
    if (value === null || value === '') {
      params.delete(key);
    } else {
      params.set(key, value);
    }
    if (key !== 'offset') params.delete('offset');
    setSearchParams(params, { replace: true });
  }

  const filters: AlertHistoryFilters = useMemo(() => {
    const out: AlertHistoryFilters = { limit, offset };
    if (locationId) out.location_id = Number(locationId);
    if (ruleId) out.rule_id = Number(ruleId);
    if (dateFrom) out.date_from = dateFrom;
    if (dateTo) out.date_to = dateTo;
    return out;
  }, [locationId, ruleId, dateFrom, dateTo, offset]);

  const historyQuery = useQuery({
    queryKey: ['alerts', 'history', filters],
    queryFn: () => listHistory(filters),
  });

  const locationsQuery = useQuery<Location[], Error>({
    queryKey: ['locations'],
    queryFn: () => listLocations(),
  });

  const rulesQuery = useQuery<AlertRule[], Error>({
    queryKey: ['alerts', 'rules'],
    queryFn: () => listRules(),
  });

  const total = historyQuery.data?.total ?? 0;
  const hasNext = offset + limit < total;
  const hasPrev = offset > 0;

  return (
    <>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <div className="grid gap-1.5">
          <Label htmlFor="hist-location">Локация</Label>
          <Select
            value={locationId ?? '__all__'}
            onValueChange={(value) =>
              setParam('location_id', value === '__all__' ? null : value)
            }
          >
            <SelectTrigger id="hist-location">
              <SelectValue placeholder="Все" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="__all__">Все</SelectItem>
              {locationsQuery.data?.map((loc) => (
                <SelectItem key={loc.id} value={String(loc.id)}>
                  {loc.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="hist-rule">Правило</Label>
          <Select
            value={ruleId ?? '__all__'}
            onValueChange={(value) =>
              setParam('rule_id', value === '__all__' ? null : value)
            }
          >
            <SelectTrigger id="hist-rule">
              <SelectValue placeholder="Все" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="__all__">Все</SelectItem>
              {rulesQuery.data?.map((rule) => (
                <SelectItem key={rule.id} value={String(rule.id)}>
                  {rule.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="hist-from">С даты</Label>
          <Input
            id="hist-from"
            type="date"
            value={dateFrom}
            onChange={(e) => setParam('date_from', e.target.value || null)}
          />
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="hist-to">По дату</Label>
          <Input
            id="hist-to"
            type="date"
            value={dateTo}
            onChange={(e) => setParam('date_to', e.target.value || null)}
          />
        </div>
      </div>

      <div className="rounded-md border bg-card">
        {historyQuery.isLoading ? (
          <LoadingState />
        ) : historyQuery.isError ? (
          <ErrorState
            message={getErrorMessage(historyQuery.error)}
            onRetry={() => void historyQuery.refetch()}
          />
        ) : (historyQuery.data?.items.length ?? 0) === 0 ? (
          <EmptyState message="Срабатываний нет." />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Время</TableHead>
                <TableHead>Правило</TableHead>
                <TableHead>Локация</TableHead>
                <TableHead>Параметр</TableHead>
                <TableHead>Условие</TableHead>
                <TableHead>Значение</TableHead>
                <TableHead>Сообщение</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {historyQuery.data?.items.map((item) => (
                <TableRow key={item.id}>
                  <TableCell className="font-mono text-xs">
                    {formatTriggeredAt(item.triggered_at)}
                  </TableCell>
                  <TableCell className="font-medium">
                    {item.rule_name}
                  </TableCell>
                  <TableCell>{item.location_name}</TableCell>
                  <TableCell>
                    {PARAMETER_LABEL[item.parameter] ?? item.parameter}
                  </TableCell>
                  <TableCell className="font-mono text-xs">
                    {formatCondition(
                      item.condition,
                      item.threshold,
                      item.threshold_max,
                    )}
                    <span className="text-muted-foreground ml-1">
                      ({CONDITION_LABEL[item.condition] ?? item.condition})
                    </span>
                  </TableCell>
                  <TableCell className="font-mono text-xs">
                    {item.value}
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {item.message}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </div>

      <div className="flex items-center justify-between text-sm text-muted-foreground">
        <span>
          {total > 0
            ? `${offset + 1}–${Math.min(offset + limit, total)} из ${total}`
            : '0 из 0'}
        </span>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={!hasPrev}
            onClick={() =>
              setParam('offset', String(Math.max(0, offset - limit)))
            }
          >
            Назад
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={!hasNext}
            onClick={() => setParam('offset', String(offset + limit))}
          >
            Вперёд
          </Button>
        </div>
      </div>
    </>
  );
}

function TelegramBindDialog({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();

  const statusQuery = useQuery({
    queryKey: ['telegram', 'status'],
    queryFn: getTelegramStatus,
    enabled: open,
  });

  const bindMutation = useMutation({
    mutationFn: issueTelegramBindCode,
    onSuccess: () =>
      void queryClient.invalidateQueries({ queryKey: ['telegram', 'status'] }),
  });

  const unbindMutation = useMutation({
    mutationFn: unbindTelegram,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['telegram', 'status'] });
      bindMutation.reset();
    },
  });

  useEffect(() => {
    if (!open) {
      bindMutation.reset();
      unbindMutation.reset();
    }
  }, [open, bindMutation, unbindMutation]);

  const code = bindMutation.data;

  return (
    <Dialog open={open} onOpenChange={(o) => (o ? null : onClose())}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Привязать Telegram</DialogTitle>
          <DialogDescription>
            Сгенерируйте одноразовый код и отправьте боту команду
            «/start &lt;код&gt;».
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-3">
          {statusQuery.isLoading ? (
            <p className="text-sm text-muted-foreground">Загрузка…</p>
          ) : statusQuery.isError ? (
            <p className="text-sm text-destructive">
              {getErrorMessage(statusQuery.error)}
            </p>
          ) : statusQuery.data?.bound ? (
            <p className="text-sm">
              Telegram привязан (chat_id: {statusQuery.data.chat_id}).
            </p>
          ) : (
            <p className="text-sm text-muted-foreground">
              Telegram не привязан.
            </p>
          )}

          {code && (
            <div className="rounded-md border bg-muted p-4 text-center">
              <div className="text-xs text-muted-foreground">Код</div>
              <div className="font-mono text-2xl tracking-widest">
                {code.code}
              </div>
              <div className="mt-1 text-xs text-muted-foreground">
                Действителен до{' '}
                {new Date(code.expires_at).toLocaleString('ru-RU')}
                {code.bot_username ? ` · @${code.bot_username}` : ''}
              </div>
            </div>
          )}

          {bindMutation.isError && (
            <p className="text-sm text-destructive" role="alert">
              {getErrorMessage(bindMutation.error)}
            </p>
          )}
          {unbindMutation.isError && (
            <p className="text-sm text-destructive" role="alert">
              {getErrorMessage(unbindMutation.error)}
            </p>
          )}
        </div>
        <DialogFooter>
          {statusQuery.data?.bound && (
            <Button
              variant="outline"
              onClick={() => unbindMutation.mutate()}
              disabled={unbindMutation.isPending}
            >
              {unbindMutation.isPending ? 'Отвязка…' : 'Отвязать'}
            </Button>
          )}
          <Button
            onClick={() => bindMutation.mutate()}
            disabled={bindMutation.isPending}
          >
            {bindMutation.isPending ? 'Генерация…' : 'Получить код'}
          </Button>
          <Button variant="outline" onClick={onClose}>
            Закрыть
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
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

function EmptyState({ message }: { message: string }) {
  return (
    <div className="flex flex-col items-center gap-3 p-12 text-center">
      <p className="text-sm text-muted-foreground">{message}</p>
    </div>
  );
}

export default AlertsPage;
