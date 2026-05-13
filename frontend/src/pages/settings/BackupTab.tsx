import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  type BackupSettings,
  type BackupUpdate,
  getBackup,
  updateBackup,
} from '@/lib/settings-api';

import { EmptyBox, ErrorBox, FormSkeleton, getErrorMessage } from './shared';

interface DraftForm {
  yandex_disk_login: string;
  yandex_disk_app_password: string;
  yandex_disk_path: string;
  retention_daily: string;
  retention_monthly: string;
}

function toDraft(b: BackupSettings): DraftForm {
  return {
    yandex_disk_login: b.yandex_disk_login ?? '',
    yandex_disk_app_password: b.yandex_disk_app_password ?? '',
    yandex_disk_path: b.yandex_disk_path,
    retention_daily: String(b.retention_daily),
    retention_monthly: String(b.retention_monthly),
  };
}

export function BackupTab() {
  const queryClient = useQueryClient();
  const backupQuery = useQuery({
    queryKey: ['settings', 'backup'],
    queryFn: getBackup,
  });

  const [draft, setDraft] = useState<DraftForm | null>(null);
  const [dirty, setDirty] = useState<Set<keyof DraftForm>>(new Set());

  useEffect(() => {
    if (backupQuery.data) {
      setDraft(toDraft(backupQuery.data));
      setDirty(new Set());
    }
  }, [backupQuery.data]);

  const mutation = useMutation({
    mutationFn: updateBackup,
    onSuccess: (data) => {
      toast.success('Сохранено');
      queryClient.setQueryData(['settings', 'backup'], data);
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  if (backupQuery.isPending) return <FormSkeleton rows={5} />;
  if (backupQuery.isError)
    return <ErrorBox message={getErrorMessage(backupQuery.error)} />;
  if (!draft) return <FormSkeleton rows={5} />;

  const setField = (key: keyof DraftForm, value: string) => {
    setDraft({ ...draft, [key]: value });
    setDirty(new Set(dirty).add(key));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const payload: BackupUpdate = {};
    if (dirty.has('yandex_disk_login'))
      payload.yandex_disk_login = draft.yandex_disk_login;
    if (dirty.has('yandex_disk_app_password'))
      payload.yandex_disk_app_password = draft.yandex_disk_app_password;
    if (dirty.has('yandex_disk_path'))
      payload.yandex_disk_path = draft.yandex_disk_path;
    if (dirty.has('retention_daily')) {
      const n = Number.parseInt(draft.retention_daily, 10);
      if (!Number.isFinite(n) || n < 1 || n > 3650) {
        toast.error('retention_daily: 1…3650');
        return;
      }
      payload.retention_daily = n;
    }
    if (dirty.has('retention_monthly')) {
      const n = Number.parseInt(draft.retention_monthly, 10);
      if (!Number.isFinite(n) || n < 1 || n > 120) {
        toast.error('retention_monthly: 1…120');
        return;
      }
      payload.retention_monthly = n;
    }
    mutation.mutate(payload);
  };

  const inputClass =
    'rounded-notion-sm border-notion-border bg-notion-bg text-notion-text placeholder:text-notion-text-subtle focus-visible:ring-1 focus-visible:ring-notion-accent-blue focus-visible:ring-offset-0';
  const numInputClass = `notion-numeric font-mono ${inputClass}`;
  const labelClass =
    'text-[11px] font-medium uppercase tracking-wide text-notion-text-muted';
  const outlineBtn =
    'rounded-notion-sm border-notion-border bg-notion-bg text-notion-text transition-colors hover:bg-notion-row-hover focus-visible:ring-1 focus-visible:ring-notion-accent-blue focus-visible:ring-offset-0';
  const primaryBtn =
    'rounded-notion-sm bg-notion-accent-blue text-white transition-colors hover:bg-notion-accent-blue/90 focus-visible:ring-1 focus-visible:ring-notion-accent-blue focus-visible:ring-offset-0';

  return (
    <div className="space-y-8">
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor="ya-login" className={labelClass}>
              Логин Яндекс.Диска
            </Label>
            <Input
              id="ya-login"
              type="text"
              autoComplete="off"
              value={draft.yandex_disk_login}
              onChange={(e) => setField('yandex_disk_login', e.target.value)}
              className={inputClass}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="ya-pass" className={labelClass}>
              Пароль приложения
            </Label>
            <Input
              id="ya-pass"
              type="password"
              autoComplete="new-password"
              value={draft.yandex_disk_app_password}
              onChange={(e) =>
                setField('yandex_disk_app_password', e.target.value)
              }
              className={inputClass}
            />
            <p className="text-xs text-notion-text-muted">
              Маска{' '}
              <code className="font-mono text-notion-text">***xxxx</code>{' '}
              означает, что секрет сохранён.
            </p>
          </div>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="ya-path" className={labelClass}>
            Путь на диске
          </Label>
          <Input
            id="ya-path"
            type="text"
            value={draft.yandex_disk_path}
            onChange={(e) => setField('yandex_disk_path', e.target.value)}
            className={`${inputClass} font-mono`}
          />
        </div>
        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor="ret-daily" className={labelClass}>
              Хранить ежедневных
            </Label>
            <Input
              id="ret-daily"
              type="number"
              min={1}
              max={3650}
              value={draft.retention_daily}
              onChange={(e) => setField('retention_daily', e.target.value)}
              className={numInputClass}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="ret-monthly" className={labelClass}>
              Хранить ежемесячных
            </Label>
            <Input
              id="ret-monthly"
              type="number"
              min={1}
              max={120}
              value={draft.retention_monthly}
              onChange={(e) => setField('retention_monthly', e.target.value)}
              className={numInputClass}
            />
          </div>
        </div>
        <div className="flex flex-wrap justify-end gap-2">
          <Button
            type="button"
            variant="outline"
            onClick={() => {
              if (backupQuery.data) {
                setDraft(toDraft(backupQuery.data));
                setDirty(new Set());
              }
            }}
            disabled={dirty.size === 0 || mutation.isPending}
            className={outlineBtn}
          >
            Сбросить
          </Button>
          <Button
            type="submit"
            disabled={dirty.size === 0 || mutation.isPending}
            className={primaryBtn}
          >
            {mutation.isPending ? 'Сохранение…' : 'Сохранить'}
          </Button>
        </div>
      </form>

      <section className="space-y-3 border-t border-notion-border pt-6">
        <div>
          <h3 className="text-sm font-medium text-notion-text">
            Ручной бэкап
          </h3>
          <p className="text-xs text-notion-text-muted">
            Автобэкап выполняется ежедневно в 04:00 МСК. Ручной запуск и
            список бэкапов появятся после реализации backend-задачи 6.2.
          </p>
        </div>
        <div className="flex gap-2">
          <Button type="button" disabled className={primaryBtn}>
            Сделать бэкап сейчас
          </Button>
        </div>
        <EmptyBox message="Список бэкапов будет доступен после задачи 6.2 (POST /api/backup/run, GET /api/backup/list)." />
      </section>
    </div>
  );
}

export default BackupTab;
