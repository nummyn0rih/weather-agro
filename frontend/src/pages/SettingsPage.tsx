import { lazy, Suspense } from 'react';
import { useSearchParams } from 'react-router-dom';

import { Skeleton } from '@/components/ui/skeleton';
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from '@/components/ui/tabs';
import { useAuthStore } from '@/stores/auth';

import { AdminOnlyNotice } from './settings/shared';

const SourcesTab = lazy(() => import('./settings/SourcesTab'));
const ApiKeysTab = lazy(() => import('./settings/ApiKeysTab'));
const TelegramTab = lazy(() => import('./settings/TelegramTab'));
const BackupTab = lazy(() => import('./settings/BackupTab'));
const CropsTab = lazy(() => import('./settings/CropsTab'));
const ProfileTab = lazy(() => import('./settings/ProfileTab'));

const TAB_VALUES = [
  'sources',
  'api-keys',
  'telegram',
  'backup',
  'crops',
  'profile',
] as const;
type TabValue = (typeof TAB_VALUES)[number];

const ADMIN_TABS: TabValue[] = [
  'sources',
  'api-keys',
  'telegram',
  'backup',
  'crops',
];

const TAB_LABELS: Record<TabValue, string> = {
  sources: 'Источники',
  'api-keys': 'API-ключи',
  telegram: 'Telegram',
  backup: 'Бэкапы',
  crops: 'Культуры',
  profile: 'Профиль',
};

function isTabValue(v: string | null): v is TabValue {
  return v !== null && (TAB_VALUES as readonly string[]).includes(v);
}

function TabSkeleton() {
  return (
    <div className="space-y-3">
      <Skeleton className="h-4 w-32 rounded-notion-sm bg-notion-surface-hover" />
      <Skeleton className="h-10 w-full rounded-notion-sm bg-notion-surface-hover" />
      <Skeleton className="h-10 w-full rounded-notion-sm bg-notion-surface-hover" />
    </div>
  );
}

export function SettingsPage() {
  const isAdmin = useAuthStore((s) => s.isAdmin);
  const [searchParams, setSearchParams] = useSearchParams();

  const defaultTab: TabValue = isAdmin ? 'sources' : 'profile';
  const tabParam = searchParams.get('tab');
  const requested = isTabValue(tabParam) ? tabParam : defaultTab;
  const visibleTabs: TabValue[] = isAdmin
    ? [...TAB_VALUES]
    : ['profile'];
  const activeTab: TabValue = visibleTabs.includes(requested)
    ? requested
    : defaultTab;

  const handleTabChange = (value: string) => {
    if (!isTabValue(value)) return;
    const next = new URLSearchParams(searchParams);
    next.set('tab', value);
    setSearchParams(next, { replace: true });
  };

  const renderTab = (tab: TabValue) => {
    const adminOnly = ADMIN_TABS.includes(tab);
    if (adminOnly && !isAdmin) return <AdminOnlyNotice />;
    switch (tab) {
      case 'sources':
        return <SourcesTab />;
      case 'api-keys':
        return <ApiKeysTab />;
      case 'telegram':
        return <TelegramTab />;
      case 'backup':
        return <BackupTab />;
      case 'crops':
        return <CropsTab />;
      case 'profile':
        return <ProfileTab />;
    }
  };

  return (
    <div className="surface-notion flex h-full flex-col gap-6 p-6 md:p-8">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight text-notion-text">
          Настройки
        </h1>
        <p className="text-sm text-notion-text-muted">
          Источники данных, секреты, Telegram-бот, бэкапы, культуры и
          параметры аккаунта.
        </p>
      </header>

      <Tabs
        value={activeTab}
        onValueChange={handleTabChange}
        orientation="vertical"
        className="flex flex-col gap-6 md:flex-row md:gap-8"
      >
        <div className="md:w-56 md:shrink-0">
          <div className="overflow-x-auto -mx-6 px-6 md:mx-0 md:overflow-visible md:px-0">
            <TabsList className="inline-flex h-auto w-max flex-row gap-0.5 rounded-none bg-transparent p-0 text-notion-text-muted md:sticky md:top-4 md:flex md:w-full md:flex-col md:items-stretch md:gap-0.5 md:border-l md:border-notion-border md:bg-transparent md:p-0">
              {visibleTabs.map((tab) => (
                <TabsTrigger
                  key={tab}
                  value={tab}
                  className="rounded-notion-sm px-3 py-1.5 text-sm font-normal text-notion-text-muted shadow-none transition-colors hover:bg-notion-row-hover hover:text-notion-text data-[state=active]:bg-notion-surface-hover data-[state=active]:text-notion-text data-[state=active]:shadow-none md:justify-start md:rounded-none md:rounded-r-notion-sm md:border-l-2 md:border-transparent md:px-3 md:py-2 md:data-[state=active]:border-notion-text md:data-[state=active]:font-medium md:data-[state=active]:bg-notion-surface-hover"
                >
                  {TAB_LABELS[tab]}
                </TabsTrigger>
              ))}
            </TabsList>
          </div>
        </div>

        <div className="min-w-0 flex-1">
          {visibleTabs.map((tab) => (
            <TabsContent
              key={tab}
              value={tab}
              className="mt-0 max-w-2xl text-notion-text"
            >
              <Suspense fallback={<TabSkeleton />}>{renderTab(tab)}</Suspense>
            </TabsContent>
          ))}
        </div>
      </Tabs>
    </div>
  );
}

export default SettingsPage;
