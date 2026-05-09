import { useEffect } from 'react';
import { Navigate, Outlet } from 'react-router-dom';
import { toast } from 'sonner';

import { Skeleton } from '@/components/ui/skeleton';
import { useAuthStore } from '@/stores/auth';

function AdminLoader() {
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

export function AdminRoute() {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const bootstrapping = useAuthStore((state) => state.bootstrapping);
  const userId = useAuthStore((state) => state.userId);
  const isAdmin = useAuthStore((state) => state.isAdmin);

  const denyAccess = isAuthenticated && !bootstrapping && userId !== null && !isAdmin;

  useEffect(() => {
    if (denyAccess) {
      toast.error('Недостаточно прав');
    }
  }, [denyAccess]);

  if (bootstrapping || (isAuthenticated && userId === null)) {
    return <AdminLoader />;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  if (!isAdmin) {
    return <Navigate to="/" replace />;
  }

  return <Outlet />;
}

export default AdminRoute;
