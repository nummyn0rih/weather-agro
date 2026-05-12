import { QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import { Suspense, lazy, useEffect } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';

import { AdminRoute } from '@/components/AdminRoute';
import { AppLayout } from '@/components/AppLayout';
import { PageFallback } from '@/components/PageFallback';
import { ProtectedRoute } from '@/components/ProtectedRoute';
import { Toaster } from '@/components/ui/sonner';
import { queryClient } from '@/lib/query-client';
import { useAuthStore } from '@/stores/auth';

const AcceptInvitePage = lazy(() => import('@/pages/AcceptInvitePage'));
const AlertsPage = lazy(() => import('@/pages/AlertsPage'));
const AnalyticsPage = lazy(() => import('@/pages/AnalyticsPage'));
const ChartsPage = lazy(() => import('@/pages/ChartsPage'));
const EventsPage = lazy(() => import('@/pages/EventsPage'));
const HomePage = lazy(() => import('@/pages/HomePage'));
const LocationsPage = lazy(() => import('@/pages/LocationsPage'));
const LoginPage = lazy(() => import('@/pages/LoginPage'));
const ReportsPage = lazy(() => import('@/pages/ReportsPage'));
const StubPage = lazy(() => import('@/pages/StubPage'));
const TablesPage = lazy(() => import('@/pages/TablesPage'));
const AdminLayout = lazy(() => import('@/pages/admin/AdminLayout'));
const InvitesPage = lazy(() => import('@/pages/admin/InvitesPage'));
const UsersPage = lazy(() => import('@/pages/admin/UsersPage'));

function App() {
  useEffect(() => {
    void useAuthStore.getState().bootstrap();
  }, []);

  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Suspense fallback={<PageFallback />}>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route
              path="/accept-invite/:token"
              element={<AcceptInvitePage />}
            />
            <Route
              element={
                <ProtectedRoute>
                  <AppLayout />
                </ProtectedRoute>
              }
            >
              <Route path="/" element={<HomePage />} />
              <Route path="/charts" element={<ChartsPage />} />
              <Route path="/tables" element={<TablesPage />} />
              <Route path="/analytics" element={<AnalyticsPage />} />
              <Route path="/events" element={<EventsPage />} />
              <Route path="/locations" element={<LocationsPage />} />
              <Route path="/alerts" element={<AlertsPage />} />
              <Route path="/reports" element={<ReportsPage />} />
              <Route
                path="/settings"
                element={<StubPage title="Настройки" />}
              />
              <Route element={<AdminRoute />}>
                <Route path="/admin" element={<AdminLayout />}>
                  <Route index element={<Navigate to="users" replace />} />
                  <Route path="users" element={<UsersPage />} />
                  <Route path="invites" element={<InvitesPage />} />
                </Route>
              </Route>
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Suspense>
      </BrowserRouter>
      <Toaster />
      {import.meta.env.DEV && <ReactQueryDevtools initialIsOpen={false} />}
    </QueryClientProvider>
  );
}

export default App;
