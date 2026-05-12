import { Skeleton } from '@/components/ui/skeleton';

export function PageFallback() {
  return (
    <div
      className="flex w-full flex-col gap-4 p-4 md:p-6"
      role="status"
      aria-label="Загрузка страницы"
      aria-busy
    >
      <Skeleton className="h-8 w-1/3" />
      <Skeleton className="h-4 w-1/2" />
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-32 w-full" />
      </div>
      <Skeleton className="h-64 w-full" />
    </div>
  );
}

export default PageFallback;
