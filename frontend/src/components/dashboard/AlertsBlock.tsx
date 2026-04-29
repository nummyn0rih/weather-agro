import { BellRing } from 'lucide-react';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

export function AlertsBlock() {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center gap-2 space-y-0">
        <BellRing className="h-4 w-4 text-muted-foreground" aria-hidden />
        <CardTitle className="text-base">Активные алерты</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-muted-foreground">
          Активных алертов нет. Раздел станет доступным после реализации
          движка правил (этап 4).
        </p>
      </CardContent>
    </Card>
  );
}

export default AlertsBlock;
