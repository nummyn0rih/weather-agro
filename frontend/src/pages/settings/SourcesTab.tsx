import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowDown, ArrowUp } from 'lucide-react';
import { useEffect, useState } from 'react';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import {
  type SourceName,
  type SourcesSettings,
  getSources,
  updateSources,
} from '@/lib/settings-api';

import { ErrorBox, FormSkeleton, getErrorMessage } from './shared';

const SOURCE_LABEL: Record<SourceName, string> = {
  open_meteo: 'Open-Meteo',
  nasa_power: 'NASA POWER',
  openweathermap: 'OpenWeatherMap',
};

const ALL_SOURCES: SourceName[] = [
  'open_meteo',
  'nasa_power',
  'openweathermap',
];

export function SourcesTab() {
  const queryClient = useQueryClient();
  const sourcesQuery = useQuery({
    queryKey: ['settings', 'sources'],
    queryFn: getSources,
  });

  const [draft, setDraft] = useState<SourcesSettings | null>(null);

  useEffect(() => {
    if (sourcesQuery.data) {
      setDraft(structuredClone(sourcesQuery.data));
    }
  }, [sourcesQuery.data]);

  const mutation = useMutation({
    mutationFn: updateSources,
    onSuccess: (data) => {
      toast.success('Настройки сохранены');
      queryClient.setQueryData(['settings', 'sources'], data);
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  if (sourcesQuery.isPending) return <FormSkeleton rows={5} />;
  if (sourcesQuery.isError)
    return <ErrorBox message={getErrorMessage(sourcesQuery.error)} />;
  if (!draft) return <FormSkeleton rows={5} />;

  const move = (idx: number, delta: number) => {
    const next = [...draft.priority];
    const newIdx = idx + delta;
    if (newIdx < 0 || newIdx >= next.length) return;
    [next[idx]!, next[newIdx]!] = [next[newIdx]!, next[idx]!];
    setDraft({ ...draft, priority: next });
  };

  const toggleEnabled = (src: SourceName, value: boolean) => {
    setDraft({
      ...draft,
      enabled: { ...draft.enabled, [src]: value },
    });
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    mutation.mutate({
      priority: draft.priority,
      enabled: draft.enabled,
      average_mode: draft.average_mode,
    });
  };

  const isDirty =
    JSON.stringify(draft) !== JSON.stringify(sourcesQuery.data);

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <section className="space-y-3">
        <div>
          <h3 className="text-sm font-medium">Приоритет источников</h3>
          <p className="text-xs text-muted-foreground">
            Порядок определяет, какой источник используется по умолчанию.
          </p>
        </div>
        <ul className="rounded-md border">
          {draft.priority.map((src, idx) => (
            <li
              key={src}
              className="flex items-center justify-between gap-2 border-b px-3 py-2 last:border-b-0"
            >
              <span className="text-sm font-medium">{SOURCE_LABEL[src]}</span>
              <div className="flex gap-1">
                <Button
                  type="button"
                  variant="outline"
                  size="icon"
                  onClick={() => move(idx, -1)}
                  disabled={idx === 0}
                  aria-label="Выше"
                >
                  <ArrowUp className="h-4 w-4" />
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="icon"
                  onClick={() => move(idx, 1)}
                  disabled={idx === draft.priority.length - 1}
                  aria-label="Ниже"
                >
                  <ArrowDown className="h-4 w-4" />
                </Button>
              </div>
            </li>
          ))}
        </ul>
      </section>

      <section className="space-y-3">
        <h3 className="text-sm font-medium">Активные источники</h3>
        <div className="space-y-2">
          {ALL_SOURCES.map((src) => (
            <div
              key={src}
              className="flex items-center justify-between rounded-md border px-3 py-2"
            >
              <Label
                htmlFor={`enabled-${src}`}
                className="text-sm font-medium"
              >
                {SOURCE_LABEL[src]}
              </Label>
              <Switch
                id={`enabled-${src}`}
                checked={draft.enabled[src] ?? false}
                onCheckedChange={(v) => toggleEnabled(src, v)}
              />
            </div>
          ))}
        </div>
      </section>

      <section className="space-y-3">
        <div className="flex items-center justify-between rounded-md border px-3 py-2">
          <div>
            <Label
              htmlFor="average-mode"
              className="text-sm font-medium"
            >
              Режим усреднения
            </Label>
            <p className="text-xs text-muted-foreground">
              GET с <code>source=average</code> возвращает среднее по
              источникам.
            </p>
          </div>
          <Switch
            id="average-mode"
            checked={draft.average_mode}
            onCheckedChange={(v) => setDraft({ ...draft, average_mode: v })}
          />
        </div>
      </section>

      <div className="flex justify-end gap-2">
        <Button
          type="button"
          variant="outline"
          onClick={() =>
            sourcesQuery.data &&
            setDraft(structuredClone(sourcesQuery.data))
          }
          disabled={!isDirty || mutation.isPending}
        >
          Сбросить
        </Button>
        <Button type="submit" disabled={!isDirty || mutation.isPending}>
          {mutation.isPending ? 'Сохранение…' : 'Сохранить'}
        </Button>
      </div>
    </form>
  );
}

export default SourcesTab;
