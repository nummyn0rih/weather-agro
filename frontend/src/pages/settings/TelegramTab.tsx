import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { getTelegram, updateTelegram } from '@/lib/settings-api';

import { ErrorBox, FormSkeleton, getErrorMessage } from './shared';

export function TelegramTab() {
  const queryClient = useQueryClient();
  const tgQuery = useQuery({
    queryKey: ['settings', 'telegram'],
    queryFn: getTelegram,
  });

  const [draftToken, setDraftToken] = useState<string>('');
  const [edited, setEdited] = useState(false);

  useEffect(() => {
    if (tgQuery.data) {
      setDraftToken(tgQuery.data.bot_token ?? '');
      setEdited(false);
    }
  }, [tgQuery.data]);

  const mutation = useMutation({
    mutationFn: updateTelegram,
    onSuccess: (data) => {
      toast.success('Сохранено');
      queryClient.setQueryData(['settings', 'telegram'], data);
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  if (tgQuery.isPending) return <FormSkeleton rows={2} />;
  if (tgQuery.isError)
    return <ErrorBox message={getErrorMessage(tgQuery.error)} />;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!edited) return;
    mutation.mutate({ bot_token: draftToken });
  };

  const handleClear = () => {
    mutation.mutate({ bot_token: '' });
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div className="space-y-2">
        <Label htmlFor="tg-token">Telegram Bot Token</Label>
        <Input
          id="tg-token"
          type="text"
          autoComplete="off"
          spellCheck={false}
          value={draftToken}
          placeholder="123456:ABC-DEF..."
          onChange={(e) => {
            setDraftToken(e.target.value);
            setEdited(true);
          }}
        />
        <p className="text-xs text-muted-foreground">
          Получите токен у @BotFather. Привязка пользователя к чату
          выполняется через вкладку «Профиль».
        </p>
      </div>
      <div className="flex flex-wrap justify-end gap-2">
        <Button
          type="button"
          variant="outline"
          onClick={handleClear}
          disabled={mutation.isPending || !tgQuery.data.bot_token}
        >
          Очистить токен
        </Button>
        <Button type="submit" disabled={!edited || mutation.isPending}>
          {mutation.isPending ? 'Сохранение…' : 'Сохранить'}
        </Button>
      </div>
    </form>
  );
}

export default TelegramTab;
