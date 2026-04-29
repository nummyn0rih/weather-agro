import { QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';

import { AppLayout } from '@/components/AppLayout';
import { ProtectedRoute } from '@/components/ProtectedRoute';
import { queryClient } from '@/lib/query-client';
import { HomePage } from '@/pages/HomePage';
import { LoginPage } from '@/pages/LoginPage';
import { StubPage } from '@/pages/StubPage';

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route
            element={
              <ProtectedRoute>
                <AppLayout />
              </ProtectedRoute>
            }
          >
            <Route path="/" element={<HomePage />} />
            <Route path="/charts" element={<StubPage title="Графики" />} />
            <Route path="/tables" element={<StubPage title="Таблицы" />} />
            <Route
              path="/analytics"
              element={<StubPage title="Аналитика" />}
            />
            <Route path="/events" element={<StubPage title="События" />} />
            <Route
              path="/locations"
              element={<StubPage title="Локации" />}
            />
            <Route path="/alerts" element={<StubPage title="Алерты" />} />
            <Route path="/reports" element={<StubPage title="Отчёты" />} />
            <Route
              path="/settings"
              element={<StubPage title="Настройки" />}
            />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
      {import.meta.env.DEV && <ReactQueryDevtools initialIsOpen={false} />}
    </QueryClientProvider>
  );
}

export default App;
