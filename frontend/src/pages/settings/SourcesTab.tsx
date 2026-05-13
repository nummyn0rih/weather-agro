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

  const switchClass =
    'h-5 w-9 data-[state=checked]:bg-notion-accent-blue data-[state=unchecked]:bg-notion-border-strong [&>span]:h-4 [&>span]:w-4 [&>span]:data-[state=checked]:translate-x-4';
  const outlineBtn =
    'rounded-notion-sm border-notion-border bg-notion-bg text-notion-text transition-colors hover:bg-notion-row-hover focus-visible:ring-1 focus-visible:ring-notion-accent-blue focus-visible:ring-offset-0';
  const primaryBtn =
    'rounded-notion-sm bg-notion-accent-blue text-white transition-colors hover:bg-notion-accent-blue/90 focus-visible:ring-1 focus-visible:ring-notion-accent-blue focus-visible:ring-offset-0';

  return (
    <form onSubmit={handleSubmit} className="space-y-8">
      <section className="space-y-3">
        <div>
          <h3 className="text-sm font-medium text-notion-text">
            Приоритет источников
          </h3>
          <p className="text-xs text-notion-text-muted">
            Порядок определяет, какой источник используется по умолчанию.
          </p>
        </div>
        <ul className="overflow-hidden rounded-notion-md border border-notion-border bg-notion-bg">
          {draft.priority.map((src, idx) => (
            <li
              key={src}
              className="flex items-center justify-between gap-2 border-b border-notion-border px-3 py-2 transition-colors last:border-b-0 hover:bg-notion-row-hover"
            >
              <span className="text-sm font-medium text-notion-text">
                {SOURCE_LABEL[src]}
              </span>
              <div className="flex gap-1">
                <Button
                  type="button"
                  variant="outline"
                  size="icon"
                  onClick={() => move(idx, -1)}
                  disabled={idx === 0}
                  aria-label="Выше"
                  className={`h-7 w-7 ${outlineBtn}`}
                >
                  <ArrowUp className="h-3.5 w-3.5" />
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="icon"
                  onClick={() => move(idx, 1)}
                  disabled={idx === draft.priority.length - 1}
                  aria-label="Ниже"
                  className={`h-7 w-7 ${outlineBtn}`}
                >
                  <ArrowDown className="h-3.5 w-3.5" />
                </Button>
              </div>
            </li>
          ))}
        </ul>
      </section>

      <section className="space-y-3">
        <h3 className="text-sm font-medium text-notion-text">
          Активные источники
        </h3>
        <div className="overflow-hidden rounded-notion-md border border-notion-border bg-notion-bg">
          {ALL_SOURCES.map((src, idx) => (
            <div
              key={src}
              className={`flex items-center justify-between px-3 py-2 transition-colors hover:bg-notion-row-hover ${idx > 0 ? 'border-t border-notion-border' : ''}`}
            >
              <Label
                htmlFor={`enabled-${src}`}
                className="cursor-pointer text-sm font-medium text-notion-text"
              >
                {SOURCE_LABEL[src]}
              </Label>
              <Switch
                id={`enabled-${src}`}
                checked={draft.enabled[src] ?? false}
                onCheckedChange={(v) => toggleEnabled(src, v)}
                className={switchClass}
              />
            </div>
          ))}
        </div>
      </section>

      <section className="space-y-3">
        <div className="flex items-center justify-between rounded-notion-md border border-notion-border bg-notion-bg px-3 py-2 transition-colors hover:bg-notion-row-hover">
          <div>
            <Label
              htmlFor="average-mode"
              className="cursor-pointer text-sm font-medium text-notion-text"
            >
              Режим усреднения
            </Label>
            <p className="text-xs text-notion-text-muted">
              GET с{' '}
              <code className="font-mono text-notion-text">
                source=average
              </code>{' '}
              возвращает среднее по источникам.
            </p>
          </div>
          <Switch
            id="average-mode"
            checked={draft.average_mode}
            onCheckedChange={(v) => setDraft({ ...draft, average_mode: v })}
            className={switchClass}
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
          className={outlineBtn}
        >
          Сбросить
        </Button>
        <Button
          type="submit"
          disabled={!isDirty || mutation.isPending}
          className={primaryBtn}
        >
          {mutation.isPending ? 'Сохранение…' : 'Сохранить'}
        </Button>
      </div>
    </form>
  );
}

export default SourcesTab;
