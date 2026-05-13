import { BellRing } from 'lucide-react';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

export function AlertsBlock() {
  return (
    <Card className="rounded-apple-lg border-0 bg-apple-surface text-apple-text shadow-apple-md transition-shadow duration-300 ease-apple hover:shadow-apple-lg">
      <CardHeader className="flex flex-row items-center gap-3 space-y-0 p-7 pb-3">
        <span className="flex h-9 w-9 items-center justify-center rounded-apple-full bg-apple-orange-pastel text-apple-orange">
          <BellRing className="h-4 w-4" aria-hidden />
        </span>
        <CardTitle className="text-lg font-semibold tracking-apple-tight">
          Активные алерты
        </CardTitle>
      </CardHeader>
      <CardContent className="p-7 pt-0">
        <p className="text-sm text-apple-text-secondary">
          Активных алертов нет. Раздел станет доступным после реализации
          движка правил (этап 4).
        </p>
      </CardContent>
    </Card>
  );
}

export default AlertsBlock;
