import { useQueryClient } from '@tanstack/react-query';
import { AnimatePresence } from 'framer-motion';
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
  Shield,
  Sun,
  Table2,
  X,
} from 'lucide-react';
import { useEffect, useState } from 'react';
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';

import { PageTransition } from '@/components/motion/PageTransition';
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

const ADMIN_NAV_ITEM: NavItem = {
  to: '/admin',
  label: 'Администрирование',
  icon: Shield,
};

export function AppLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const queryClient = useQueryClient();
  const username = useAuthStore((state) => state.username);
  const isAdmin = useAuthStore((state) => state.isAdmin);
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
    <div className="flex min-h-screen bg-apple-bg text-apple-text">
      <aside className="hidden w-60 shrink-0 flex-col border-r border-apple-separator bg-apple-surface/70 backdrop-blur-xl backdrop-saturate-150 transition-[width,background-color] duration-300 ease-apple supports-[backdrop-filter]:bg-apple-surface/60 md:flex">
        <SidebarContent isAdmin={isAdmin} />
      </aside>

      {isDrawerOpen && (
        <div className="fixed inset-0 z-40 md:hidden" role="dialog" aria-modal>
          <div
            className="absolute inset-0 bg-black/40 backdrop-blur-sm animate-in fade-in duration-200 ease-apple"
            onClick={() => setIsDrawerOpen(false)}
            aria-hidden
          />
          <aside className="absolute inset-y-0 left-0 flex w-64 flex-col border-r border-apple-separator bg-apple-surface/85 backdrop-blur-xl backdrop-saturate-150 shadow-apple-xl animate-in slide-in-from-left duration-300 ease-apple supports-[backdrop-filter]:bg-apple-surface/75">
            <div className="flex items-center justify-between border-b border-apple-separator px-4 py-3">
              <span className="text-sm font-semibold tracking-apple-tight text-apple-text">
                Weather Agro
              </span>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setIsDrawerOpen(false)}
                aria-label="Закрыть меню"
                className="h-11 w-11 rounded-apple-full text-apple-text-secondary transition-colors duration-200 ease-apple hover:bg-apple-blue-pastel hover:text-apple-blue focus-visible:ring-2 focus-visible:ring-apple-blue focus-visible:ring-offset-0 md:h-10 md:w-10"
              >
                <X className="h-5 w-5" />
              </Button>
            </div>
            <SidebarContent showHeader={false} isAdmin={isAdmin} />
          </aside>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex items-center justify-between border-b border-apple-separator bg-apple-surface/70 px-4 py-3 backdrop-blur-xl backdrop-saturate-150 supports-[backdrop-filter]:bg-apple-surface/60 md:px-6">
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="icon"
              className="h-11 w-11 rounded-apple-full text-apple-text-secondary transition-colors duration-200 ease-apple hover:bg-apple-blue-pastel hover:text-apple-blue focus-visible:ring-2 focus-visible:ring-apple-blue focus-visible:ring-offset-0 md:hidden"
              onClick={() => setIsDrawerOpen(true)}
              aria-label="Открыть меню"
            >
              <Menu className="h-5 w-5" />
            </Button>
            <span className="text-sm font-semibold tracking-apple-tight text-apple-text md:hidden">
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
              className="h-11 w-11 rounded-apple-full text-apple-text-secondary transition-colors duration-200 ease-apple hover:bg-apple-blue-pastel hover:text-apple-blue focus-visible:ring-2 focus-visible:ring-apple-blue focus-visible:ring-offset-0 md:h-10 md:w-10"
            >
              {theme === 'dark' ? (
                <Sun className="h-5 w-5" />
              ) : (
                <Moon className="h-5 w-5" />
              )}
            </Button>
            {username && (
              <span className="hidden text-sm text-apple-text-secondary sm:inline">
                {username}
              </span>
            )}
            <Button
              variant="outline"
              size="sm"
              onClick={handleLogout}
              className="h-11 rounded-apple-full border-apple-separator bg-apple-surface/80 text-apple-blue transition-colors duration-200 ease-apple hover:bg-apple-blue-pastel hover:text-apple-blue focus-visible:ring-2 focus-visible:ring-apple-blue focus-visible:ring-offset-0 md:h-9"
            >
              Выйти
            </Button>
          </div>
        </header>
        <main className="flex-1 min-w-0">
          <AnimatePresence mode="wait" initial={false}>
            <PageTransition key={location.pathname} className="h-full">
              <Outlet />
            </PageTransition>
          </AnimatePresence>
        </main>
      </div>
    </div>
  );
}

interface SidebarContentProps {
  showHeader?: boolean;
  isAdmin: boolean;
}

function SidebarContent({ showHeader = true, isAdmin }: SidebarContentProps) {
  const items = isAdmin ? [...NAV_ITEMS, ADMIN_NAV_ITEM] : NAV_ITEMS;
  return (
    <>
      {showHeader && (
        <div className="border-b border-apple-separator px-4 py-4">
          <span className="text-base font-semibold tracking-apple-tight text-apple-text">
            Weather Agro
          </span>
        </div>
      )}
      <nav className="flex-1 overflow-y-auto px-2 py-4">
        <ul className="flex flex-col gap-1">
          {items.map((item) => (
            <li key={item.to}>
              <NavLink
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  cn(
                    'flex min-h-[44px] items-center gap-3 rounded-apple-md px-3 py-2 text-sm transition-all duration-200 ease-apple focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-apple-blue focus-visible:ring-offset-0 md:min-h-0',
                    isActive
                      ? 'bg-apple-blue-pastel font-medium text-apple-blue'
                      : 'text-apple-text-secondary hover:bg-apple-blue-pastel/60 hover:text-apple-text',
                  )
                }
              >
                <item.icon className="h-[18px] w-[18px] shrink-0" aria-hidden strokeWidth={1.75} />
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
