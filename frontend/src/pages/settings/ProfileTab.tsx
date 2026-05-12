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

  return (
    <div className="space-y-10">
      <section className="space-y-3">
        <div>
          <h3 className="text-sm font-medium">Профиль</h3>
          <p className="text-xs text-muted-foreground">
            Имя пользователя: <span className="font-medium">{username}</span>
          </p>
        </div>
      </section>

      <section className="space-y-4 border-t pt-6">
        <div>
          <h3 className="text-sm font-medium">Смена пароля</h3>
          <p className="text-xs text-muted-foreground">
            После смены пароля все ранее выданные токены инвалидируются.
          </p>
        </div>
        <form onSubmit={handlePasswordSubmit} className="space-y-3">
          <div className="space-y-2">
            <Label htmlFor="old-pwd">Текущий пароль</Label>
            <Input
              id="old-pwd"
              type="password"
              autoComplete="current-password"
              value={oldPwd}
              onChange={(e) => setOldPwd(e.target.value)}
              required
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="new-pwd">Новый пароль (≥ 8 символов)</Label>
            <Input
              id="new-pwd"
              type="password"
              autoComplete="new-password"
              value={newPwd}
              onChange={(e) => setNewPwd(e.target.value)}
              required
              minLength={8}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="confirm-pwd">Повторите новый пароль</Label>
            <Input
              id="confirm-pwd"
              type="password"
              autoComplete="new-password"
              value={confirmPwd}
              onChange={(e) => setConfirmPwd(e.target.value)}
              required
              minLength={8}
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
            >
              {passwordMutation.isPending ? 'Сохранение…' : 'Сменить пароль'}
            </Button>
          </div>
        </form>
      </section>

      <section className="space-y-4 border-t pt-6">
        <div>
          <h3 className="text-sm font-medium">Telegram</h3>
          <p className="text-xs text-muted-foreground">
            Привяжите аккаунт к боту, чтобы получать алерты в Telegram.
          </p>
        </div>
        {statusQuery.isPending ? (
          <FormSkeleton rows={1} />
        ) : statusQuery.isError ? (
          <ErrorBox message={getErrorMessage(statusQuery.error)} />
        ) : statusQuery.data.bound ? (
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-md border p-3">
            <div>
              <p className="text-sm font-medium">Привязан</p>
              <p className="text-xs text-muted-foreground">
                chat_id: <code>{statusQuery.data.chat_id}</code>
              </p>
            </div>
            <Button
              variant="outline"
              onClick={() => unbindMutation.mutate()}
              disabled={unbindMutation.isPending}
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
            >
              {issueMutation.isPending ? 'Генерация…' : 'Привязать Telegram'}
            </Button>
            {bindCode && (
              <div className="rounded-md border p-3 space-y-2">
                <p className="text-sm">
                  Отправьте боту команду{' '}
                  <code>/start {bindCode.code}</code>
                </p>
                <div className="flex items-center gap-2">
                  <Input value={bindCode.code} readOnly />
                  <Button
                    type="button"
                    variant="outline"
                    size="icon"
                    onClick={() => {
                      void copyCode();
                    }}
                    aria-label="Скопировать код"
                  >
                    <Copy className="h-4 w-4" />
                  </Button>
                </div>
                <p className="text-xs text-muted-foreground">
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
