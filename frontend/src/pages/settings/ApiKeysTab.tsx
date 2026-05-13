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

  const inputClass =
    'rounded-notion-sm border-notion-border bg-notion-bg font-mono text-notion-text placeholder:text-notion-text-subtle focus-visible:ring-1 focus-visible:ring-notion-accent-blue focus-visible:ring-offset-0';
  const labelClass =
    'text-[11px] font-medium uppercase tracking-wide text-notion-text-muted';
  const outlineBtn =
    'rounded-notion-sm border-notion-border bg-notion-bg text-notion-text transition-colors hover:bg-notion-row-hover focus-visible:ring-1 focus-visible:ring-notion-accent-blue focus-visible:ring-offset-0';
  const primaryBtn =
    'rounded-notion-sm bg-notion-accent-blue text-white transition-colors hover:bg-notion-accent-blue/90 focus-visible:ring-1 focus-visible:ring-notion-accent-blue focus-visible:ring-offset-0';

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div className="space-y-1.5">
        <Label htmlFor="owm-key" className={labelClass}>
          OpenWeatherMap API Key
        </Label>
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
          className={inputClass}
        />
        <p className="text-xs text-notion-text-muted">
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
          className={outlineBtn}
        >
          Очистить ключ
        </Button>
        <Button
          type="submit"
          disabled={!edited || mutation.isPending}
          className={primaryBtn}
        >
          {mutation.isPending ? 'Сохранение…' : 'Сохранить'}
        </Button>
      </div>
    </form>
  );
}

export default ApiKeysTab;
