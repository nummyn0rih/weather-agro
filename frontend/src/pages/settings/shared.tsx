import axios from 'axios';

import { Skeleton } from '@/components/ui/skeleton';

export function getErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data as
      | {
          detail?:
            | string
            | { msg?: string; message?: string }
            | { msg?: string }[];
        }
      | undefined;
    const detail = data?.detail;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail) && detail.length > 0) {
      const first = detail[0];
      if (first?.msg) return first.msg;
    }
    if (detail && typeof detail === 'object' && 'message' in detail) {
      const message = (detail as { message?: string }).message;
      if (typeof message === 'string') return message;
    }
    return error.message;
  }
  return error instanceof Error ? error.message : 'Неизвестная ошибка';
}

export function FormSkeleton({ rows = 4 }: { rows?: number }) {
  return (
    <div className="space-y-4">
      {Array.from({ length: rows }).map((_, idx) => (
        <div key={idx} className="space-y-2">
          <Skeleton className="h-3 w-32 rounded-notion-sm bg-notion-surface-hover" />
          <Skeleton className="h-9 w-full rounded-notion-sm bg-notion-surface-hover" />
        </div>
      ))}
    </div>
  );
}

export function ErrorBox({ message }: { message: string }) {
  return (
    <div className="rounded-notion-md border border-notion-border bg-[var(--notion-chip-red-bg)]/40 p-4">
      <p className="text-sm font-medium text-[var(--notion-chip-red-fg)]">
        Не удалось загрузить данные
      </p>
      <p className="mt-1 text-sm text-notion-text-muted">{message}</p>
    </div>
  );
}

export function EmptyBox({ message }: { message: string }) {
  return (
    <div className="rounded-notion-md border border-dashed border-notion-border bg-notion-bg-secondary p-6 text-center text-sm text-notion-text-muted">
      {message}
    </div>
  );
}

export function AdminOnlyNotice() {
  return (
    <div className="rounded-notion-md border border-notion-border bg-notion-bg-secondary p-6 text-sm text-notion-text-muted">
      Раздел доступен только администраторам.
    </div>
  );
}
