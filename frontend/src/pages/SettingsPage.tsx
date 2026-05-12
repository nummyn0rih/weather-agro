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
      <Skeleton className="h-4 w-32" />
      <Skeleton className="h-10 w-full" />
      <Skeleton className="h-10 w-full" />
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
    <div className="flex h-full flex-col gap-6 p-4 md:p-8">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">Настройки</h1>
        <p className="text-sm text-muted-foreground">
          Источники данных, секреты, Telegram-бот, бэкапы, культуры и
          параметры аккаунта.
        </p>
      </header>

      <Tabs value={activeTab} onValueChange={handleTabChange}>
        <div className="overflow-x-auto -mx-4 px-4 md:mx-0 md:px-0">
          <TabsList className="h-auto flex-wrap justify-start">
            {visibleTabs.map((tab) => (
              <TabsTrigger key={tab} value={tab}>
                {TAB_LABELS[tab]}
              </TabsTrigger>
            ))}
          </TabsList>
        </div>

        {visibleTabs.map((tab) => (
          <TabsContent key={tab} value={tab} className="max-w-2xl">
            <Suspense fallback={<TabSkeleton />}>{renderTab(tab)}</Suspense>
          </TabsContent>
        ))}
      </Tabs>
    </div>
  );
}

export default SettingsPage;
