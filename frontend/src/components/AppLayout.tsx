import { useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';

import { Button } from '@/components/ui/button';
import { logout as logoutRequest } from '@/lib/auth-api';
import { useAuthStore } from '@/stores/auth';

interface AppLayoutProps {
  children: React.ReactNode;
}

export function AppLayout({ children }: AppLayoutProps) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const username = useAuthStore((state) => state.username);
  const clearSession = useAuthStore((state) => state.clearSession);

  const handleLogout = () => {
    void (async () => {
      await logoutRequest();
      clearSession();
      queryClient.clear();
      await navigate('/login', { replace: true });
    })();
  };

  return (
    <div className="flex min-h-screen flex-col bg-background text-foreground">
      <header className="flex items-center justify-between border-b px-6 py-3">
        <span className="text-sm font-semibold tracking-tight">
          Weather Agro
        </span>
        <div className="flex items-center gap-3">
          {username && (
            <span className="text-sm text-muted-foreground">{username}</span>
          )}
          <Button variant="outline" size="sm" onClick={handleLogout}>
            Выйти
          </Button>
        </div>
      </header>
      <main className="flex-1">{children}</main>
    </div>
  );
}

export default AppLayout;
