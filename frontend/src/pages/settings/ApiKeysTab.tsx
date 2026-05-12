import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { getApiKeys, updateApiKeys } from '@/lib/settings-api';

import { ErrorBox, FormSkeleton, getErrorMessage } from './shared';

export function ApiKeysTab() {
  const queryClient = useQueryClient();
  const keysQuery = useQuery({
    queryKey: ['settings', 'api-keys'],
    queryFn: getApiKeys,
  });

  const [draftKey, setDraftKey] = useState<string>('');
  const [edited, setEdited] = useState(false);

  useEffect(() => {
    if (keysQuery.data) {
      setDraftKey(keysQuery.data.openweathermap_api_key ?? '');
      setEdited(false);
    }
  }, [keysQuery.data]);

  const mutation = useMutation({
    mutationFn: updateApiKeys,
    onSuccess: (data) => {
      toast.success('Сохранено');
      queryClient.setQueryData(['settings', 'api-keys'], data);
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  if (keysQuery.isPending) return <FormSkeleton rows={2} />;
  if (keysQuery.isError)
    return <ErrorBox message={getErrorMessage(keysQuery.error)} />;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!edited) return;
    mutation.mutate({ openweathermap_api_key: draftKey });
  };

  const handleClear = () => {
    mutation.mutate({ openweathermap_api_key: '' });
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div className="space-y-2">
        <Label htmlFor="owm-key">OpenWeatherMap API Key</Label>
        <Input
          id="owm-key"
          type="text"
          autoComplete="off"
          spellCheck={false}
          value={draftKey}
          placeholder="Введите ключ"
          onChange={(e) => {
            setDraftKey(e.target.value);
            setEdited(true);
          }}
        />
        <p className="text-xs text-muted-foreground">
          Текущее значение замаскировано (последние 4 символа). Чтобы
          сохранить ключ, очистите поле и введите новое значение.
        </p>
      </div>
      <div className="flex flex-wrap justify-end gap-2">
        <Button
          type="button"
          variant="outline"
          onClick={handleClear}
          disabled={mutation.isPending || !keysQuery.data.openweathermap_api_key}
        >
          Очистить ключ
        </Button>
        <Button type="submit" disabled={!edited || mutation.isPending}>
          {mutation.isPending ? 'Сохранение…' : 'Сохранить'}
        </Button>
      </div>
    </form>
  );
}

export default ApiKeysTab;
