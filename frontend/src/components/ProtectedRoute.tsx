import type { ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router-dom';

import { Skeleton } from '@/components/ui/skeleton';
import { useAuthStore } from '@/stores/auth';

interface ProtectedRouteProps {
  children: ReactNode;
}

function AuthLoader() {
  return (
    <div
      className="flex min-h-screen items-center justify-center bg-background p-4"
      role="status"
      aria-label="Загрузка"
    >
      <div className="w-full max-w-sm space-y-3">
        <Skeleton className="h-6 w-32" />
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-3/4" />
      </div>
    </div>
  );
}

export function ProtectedRoute({ children }: ProtectedRouteProps) {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const bootstrapping = useAuthStore((state) => state.bootstrapping);
  const location = useLocation();

  if (bootstrapping) {
    return <AuthLoader />;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  return <>{children}</>;
}

export default ProtectedRoute;
