import { useQueryClient } from '@tanstack/react-query';
import {
  BarChart3,
  BellRing,
  FileText,
  LayoutDashboard,
  LineChart,
  type LucideIcon,
  MapPin,
  Menu,
  Moon,
  NotebookPen,
  Settings,
  Sun,
  Table2,
  X,
} from 'lucide-react';
import { useEffect, useState } from 'react';
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';

import { Button } from '@/components/ui/button';
import { logout as logoutRequest } from '@/lib/auth-api';
import { cn } from '@/lib/utils';
import { useAuthStore } from '@/stores/auth';
import { useThemeStore } from '@/stores/theme';

interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  end?: boolean;
}

const NAV_ITEMS: NavItem[] = [
  { to: '/', label: 'Дашборд', icon: LayoutDashboard, end: true },
  { to: '/charts', label: 'Графики', icon: LineChart },
  { to: '/tables', label: 'Таблицы', icon: Table2 },
  { to: '/analytics', label: 'Аналитика', icon: BarChart3 },
  { to: '/events', label: 'События', icon: NotebookPen },
  { to: '/locations', label: 'Локации', icon: MapPin },
  { to: '/alerts', label: 'Алерты', icon: BellRing },
  { to: '/reports', label: 'Отчёты', icon: FileText },
  { to: '/settings', label: 'Настройки', icon: Settings },
];

export function AppLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const queryClient = useQueryClient();
  const username = useAuthStore((state) => state.username);
  const clearSession = useAuthStore((state) => state.clearSession);
  const theme = useThemeStore((state) => state.theme);
  const toggleTheme = useThemeStore((state) => state.toggleTheme);

  const [isDrawerOpen, setIsDrawerOpen] = useState(false);

  useEffect(() => {
    setIsDrawerOpen(false);
  }, [location.pathname]);

  const handleLogout = () => {
    void (async () => {
      await logoutRequest();
      clearSession();
      queryClient.clear();
      await navigate('/login', { replace: true });
    })();
  };

  return (
    <div className="flex min-h-screen bg-background text-foreground">
      <aside className="hidden w-60 shrink-0 flex-col border-r bg-card md:flex">
        <SidebarContent />
      </aside>

      {isDrawerOpen && (
        <div className="fixed inset-0 z-40 md:hidden" role="dialog" aria-modal>
          <div
            className="absolute inset-0 bg-black/50"
            onClick={() => setIsDrawerOpen(false)}
            aria-hidden
          />
          <aside className="absolute inset-y-0 left-0 flex w-64 flex-col border-r bg-card shadow-xl">
            <div className="flex items-center justify-between px-4 py-3 border-b">
              <span className="text-sm font-semibold tracking-tight">
                Weather Agro
              </span>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setIsDrawerOpen(false)}
                aria-label="Закрыть меню"
              >
                <X className="h-5 w-5" />
              </Button>
            </div>
            <SidebarContent showHeader={false} />
          </aside>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between border-b bg-card px-4 py-3 md:px-6">
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="icon"
              className="md:hidden"
              onClick={() => setIsDrawerOpen(true)}
              aria-label="Открыть меню"
            >
              <Menu className="h-5 w-5" />
            </Button>
            <span className="text-sm font-semibold tracking-tight md:hidden">
              Weather Agro
            </span>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="icon"
              onClick={toggleTheme}
              aria-label={
                theme === 'dark'
                  ? 'Переключить на светлую тему'
                  : 'Переключить на тёмную тему'
              }
            >
              {theme === 'dark' ? (
                <Sun className="h-5 w-5" />
              ) : (
                <Moon className="h-5 w-5" />
              )}
            </Button>
            {username && (
              <span className="hidden text-sm text-muted-foreground sm:inline">
                {username}
              </span>
            )}
            <Button variant="outline" size="sm" onClick={handleLogout}>
              Выйти
            </Button>
          </div>
        </header>
        <main className="flex-1 min-w-0">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

interface SidebarContentProps {
  showHeader?: boolean;
}

function SidebarContent({ showHeader = true }: SidebarContentProps) {
  return (
    <>
      {showHeader && (
        <div className="px-4 py-4 border-b">
          <span className="text-sm font-semibold tracking-tight">
            Weather Agro
          </span>
        </div>
      )}
      <nav className="flex-1 overflow-y-auto px-2 py-3">
        <ul className="flex flex-col gap-1">
          {NAV_ITEMS.map((item) => (
            <li key={item.to}>
              <NavLink
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  cn(
                    'flex items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors',
                    isActive
                      ? 'bg-accent text-accent-foreground font-medium'
                      : 'text-muted-foreground hover:bg-accent/50 hover:text-foreground',
                  )
                }
              >
                <item.icon className="h-4 w-4" aria-hidden />
                <span>{item.label}</span>
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
    </>
  );
}

export default AppLayout;
