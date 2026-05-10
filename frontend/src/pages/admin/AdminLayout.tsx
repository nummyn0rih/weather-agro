import { NavLink, Outlet } from 'react-router-dom';

import { cn } from '@/lib/utils';

interface TabItem {
  to: string;
  label: string;
}

const TABS: TabItem[] = [
  { to: '/admin/users', label: 'Пользователи' },
  { to: '/admin/invites', label: 'Инвайты' },
];

export function AdminLayout() {
  return (
    <div className="flex h-full flex-col">
      <div className="border-b px-6 pt-6 md:px-8">
        <h1 className="text-2xl font-semibold tracking-tight">
          Администрирование
        </h1>
        <nav className="mt-4 flex gap-1" aria-label="Разделы администрирования">
          {TABS.map((tab) => (
            <NavLink
              key={tab.to}
              to={tab.to}
              className={({ isActive }) =>
                cn(
                  '-mb-px border-b-2 px-4 py-2 text-sm font-medium transition-colors',
                  isActive
                    ? 'border-primary text-foreground'
                    : 'border-transparent text-muted-foreground hover:text-foreground',
                )
              }
            >
              {tab.label}
            </NavLink>
          ))}
        </nav>
      </div>
      <div className="flex-1 min-h-0">
        <Outlet />
      </div>
    </div>
  );
}

export default AdminLayout;
