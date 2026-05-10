import { QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import { useEffect } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';

import { AdminRoute } from '@/components/AdminRoute';
import { AppLayout } from '@/components/AppLayout';
import { ProtectedRoute } from '@/components/ProtectedRoute';
import { Toaster } from '@/components/ui/sonner';
import { queryClient } from '@/lib/query-client';
import { AcceptInvitePage } from '@/pages/AcceptInvitePage';
import { AlertsPage } from '@/pages/AlertsPage';
import { AnalyticsPage } from '@/pages/AnalyticsPage';
import { ChartsPage } from '@/pages/ChartsPage';
import { EventsPage } from '@/pages/EventsPage';
import { HomePage } from '@/pages/HomePage';
import { LocationsPage } from '@/pages/LocationsPage';
import { LoginPage } from '@/pages/LoginPage';
import { ReportsPage } from '@/pages/ReportsPage';
import { StubPage } from '@/pages/StubPage';
import { TablesPage } from '@/pages/TablesPage';
import { AdminLayout } from '@/pages/admin/AdminLayout';
import { InvitesPage } from '@/pages/admin/InvitesPage';
import { UsersPage } from '@/pages/admin/UsersPage';
import { useAuthStore } from '@/stores/auth';

function App() {
  useEffect(() => {
    void useAuthStore.getState().bootstrap();
  }, []);

  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
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
      </BrowserRouter>
      <Toaster />
      {import.meta.env.DEV && <ReactQueryDevtools initialIsOpen={false} />}
    </QueryClientProvider>
  );
}

export default App;
