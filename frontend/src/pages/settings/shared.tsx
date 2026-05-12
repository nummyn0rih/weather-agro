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
          <Skeleton className="h-4 w-32" />
          <Skeleton className="h-10 w-full" />
        </div>
      ))}
    </div>
  );
}

export function ErrorBox({ message }: { message: string }) {
  return (
    <div className="rounded-md border border-destructive/50 bg-destructive/5 p-4">
      <p className="text-sm font-medium text-destructive">
        Не удалось загрузить данные
      </p>
      <p className="mt-1 text-sm text-muted-foreground">{message}</p>
    </div>
  );
}

export function EmptyBox({ message }: { message: string }) {
  return (
    <div className="rounded-md border p-6 text-center text-sm text-muted-foreground">
      {message}
    </div>
  );
}

export function AdminOnlyNotice() {
  return (
    <div className="rounded-md border p-6 text-sm text-muted-foreground">
      Раздел доступен только администраторам.
    </div>
  );
}
