import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Copy, Link2Off } from 'lucide-react';
import { useState } from 'react';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  type TelegramBindCode,
  changePassword,
  getTelegramBindStatus,
  issueTelegramBindCode,
  unbindTelegram,
} from '@/lib/settings-api';
import { useAuthStore } from '@/stores/auth';

import { ErrorBox, FormSkeleton, getErrorMessage } from './shared';

export function ProfileTab() {
  const queryClient = useQueryClient();
  const username = useAuthStore((s) => s.username);
  const refreshUserInfo = useAuthStore((s) => s.refreshUserInfo);

  const [oldPwd, setOldPwd] = useState('');
  const [newPwd, setNewPwd] = useState('');
  const [confirmPwd, setConfirmPwd] = useState('');

  const passwordMutation = useMutation({
    mutationFn: ({ o, n }: { o: string; n: string }) => changePassword(o, n),
    onSuccess: () => {
      toast.success(
        'Пароль изменён. Все старые токены инвалидированы — войдите снова.',
      );
      setOldPwd('');
      setNewPwd('');
      setConfirmPwd('');
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  const statusQuery = useQuery({
    queryKey: ['telegram', 'status'],
    queryFn: getTelegramBindStatus,
  });

  const [bindCode, setBindCode] = useState<TelegramBindCode | null>(null);

  const issueMutation = useMutation({
    mutationFn: issueTelegramBindCode,
    onSuccess: (data) => {
      setBindCode(data);
      toast.success('Код выдан');
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  const unbindMutation = useMutation({
    mutationFn: unbindTelegram,
    onSuccess: () => {
      toast.success('Telegram отвязан');
      setBindCode(null);
      void queryClient.invalidateQueries({ queryKey: ['telegram', 'status'] });
      void refreshUserInfo();
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  const handlePasswordSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (newPwd.length < 8) {
      toast.error('Новый пароль ≥ 8 символов');
      return;
    }
    if (newPwd !== confirmPwd) {
      toast.error('Пароли не совпадают');
      return;
    }
    if (newPwd === oldPwd) {
      toast.error('Новый пароль должен отличаться от старого');
      return;
    }
    passwordMutation.mutate({ o: oldPwd, n: newPwd });
  };

  const copyCode = async () => {
    if (!bindCode) return;
    try {
      await navigator.clipboard.writeText(bindCode.code);
      toast.success('Скопировано');
    } catch {
      toast.error('Не удалось скопировать');
    }
  };

  const inputClass =
    'rounded-notion-sm border-notion-border bg-notion-bg text-notion-text placeholder:text-notion-text-subtle focus-visible:ring-1 focus-visible:ring-notion-accent-blue focus-visible:ring-offset-0';
  const labelClass =
    'text-[11px] font-medium uppercase tracking-wide text-notion-text-muted';
  const primaryBtn =
    'rounded-notion-sm bg-notion-accent-blue text-white transition-colors hover:bg-notion-accent-blue/90 focus-visible:ring-1 focus-visible:ring-notion-accent-blue focus-visible:ring-offset-0';
  const outlineBtn =
    'rounded-notion-sm border-notion-border bg-notion-bg text-notion-text transition-colors hover:bg-notion-row-hover focus-visible:ring-1 focus-visible:ring-notion-accent-blue focus-visible:ring-offset-0';

  return (
    <div className="space-y-8">
      <section className="space-y-2">
        <h3 className="text-sm font-medium text-notion-text">Профиль</h3>
        <p className="text-xs text-notion-text-muted">
          Имя пользователя:{' '}
          <span className="font-medium text-notion-text">{username}</span>
        </p>
      </section>

      <section className="space-y-4 border-t border-notion-border pt-6">
        <div>
          <h3 className="text-sm font-medium text-notion-text">
            Смена пароля
          </h3>
          <p className="text-xs text-notion-text-muted">
            После смены пароля все ранее выданные токены инвалидируются.
          </p>
        </div>
        <form onSubmit={handlePasswordSubmit} className="space-y-3">
          <div className="space-y-1.5">
            <Label htmlFor="old-pwd" className={labelClass}>
              Текущий пароль
            </Label>
            <Input
              id="old-pwd"
              type="password"
              autoComplete="current-password"
              value={oldPwd}
              onChange={(e) => setOldPwd(e.target.value)}
              required
              className={inputClass}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="new-pwd" className={labelClass}>
              Новый пароль (≥ 8 символов)
            </Label>
            <Input
              id="new-pwd"
              type="password"
              autoComplete="new-password"
              value={newPwd}
              onChange={(e) => setNewPwd(e.target.value)}
              required
              minLength={8}
              className={inputClass}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="confirm-pwd" className={labelClass}>
              Повторите новый пароль
            </Label>
            <Input
              id="confirm-pwd"
              type="password"
              autoComplete="new-password"
              value={confirmPwd}
              onChange={(e) => setConfirmPwd(e.target.value)}
              required
              minLength={8}
              className={inputClass}
            />
          </div>
          <div className="flex justify-end">
            <Button
              type="submit"
              disabled={
                passwordMutation.isPending ||
                oldPwd === '' ||
                newPwd === '' ||
                confirmPwd === ''
              }
              className={primaryBtn}
            >
              {passwordMutation.isPending ? 'Сохранение…' : 'Сменить пароль'}
            </Button>
          </div>
        </form>
      </section>

      <section className="space-y-4 border-t border-notion-border pt-6">
        <div>
          <h3 className="text-sm font-medium text-notion-text">Telegram</h3>
          <p className="text-xs text-notion-text-muted">
            Привяжите аккаунт к боту, чтобы получать алерты в Telegram.
          </p>
        </div>
        {statusQuery.isPending ? (
          <FormSkeleton rows={1} />
        ) : statusQuery.isError ? (
          <ErrorBox message={getErrorMessage(statusQuery.error)} />
        ) : statusQuery.data.bound ? (
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-notion-md border border-notion-border bg-notion-bg-secondary p-3 transition-colors hover:bg-notion-surface-hover">
            <div>
              <p className="text-sm font-medium text-notion-text">Привязан</p>
              <p className="text-xs text-notion-text-muted">
                chat_id:{' '}
                <code className="notion-numeric font-mono text-notion-text">
                  {statusQuery.data.chat_id}
                </code>
              </p>
            </div>
            <Button
              variant="outline"
              onClick={() => unbindMutation.mutate()}
              disabled={unbindMutation.isPending}
              className={outlineBtn}
            >
              <Link2Off className="mr-2 h-4 w-4" />
              Отвязать
            </Button>
          </div>
        ) : (
          <div className="space-y-3">
            <Button
              type="button"
              onClick={() => issueMutation.mutate()}
              disabled={issueMutation.isPending}
              className={primaryBtn}
            >
              {issueMutation.isPending ? 'Генерация…' : 'Привязать Telegram'}
            </Button>
            {bindCode && (
              <div className="space-y-2 rounded-notion-md border border-notion-border bg-notion-bg-secondary p-3">
                <p className="text-sm text-notion-text">
                  Отправьте боту команду{' '}
                  <code className="font-mono text-notion-text">
                    /start {bindCode.code}
                  </code>
                </p>
                <div className="flex items-center gap-2">
                  <Input
                    value={bindCode.code}
                    readOnly
                    className={`${inputClass} notion-numeric font-mono`}
                  />
                  <Button
                    type="button"
                    variant="outline"
                    size="icon"
                    onClick={() => {
                      void copyCode();
                    }}
                    aria-label="Скопировать код"
                    className={outlineBtn}
                  >
                    <Copy className="h-4 w-4" />
                  </Button>
                </div>
                <p className="text-xs text-notion-text-muted">
                  Код действует до{' '}
                  {new Date(bindCode.expires_at).toLocaleString('ru-RU')}.
                </p>
              </div>
            )}
          </div>
        )}
      </section>
    </div>
  );
}

export default ProfileTab;
