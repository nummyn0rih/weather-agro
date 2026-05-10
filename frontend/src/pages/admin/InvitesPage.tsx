import { useQuery } from '@tanstack/react-query';
import axios from 'axios';

import { Badge, type BadgeProps } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { type InviteStatus, listInvites } from '@/lib/admin-api';

const dateFormatter = new Intl.DateTimeFormat('ru-RU', {
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
});

function formatDate(value: string): string {
  return dateFormatter.format(new Date(value));
}

const STATUS_LABEL: Record<InviteStatus, string> = {
  pending: 'Ожидает',
  accepted: 'Принят',
  revoked: 'Отозван',
  expired: 'Истёк',
};

const STATUS_VARIANT: Record<InviteStatus, BadgeProps['variant']> = {
  pending: 'default',
  accepted: 'secondary',
  revoked: 'destructive',
  expired: 'outline',
};

function getErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data as
      | { detail?: string | { msg?: string }[] }
      | undefined;
    const detail = data?.detail;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail) && detail.length > 0) {
      const first = detail[0];
      if (first?.msg) return first.msg;
    }
    return error.message;
  }
  return error instanceof Error ? error.message : 'Неизвестная ошибка';
}

export function InvitesPage() {
  const invitesQuery = useQuery({
    queryKey: ['admin', 'invites'],
    queryFn: listInvites,
  });

  return (
    <div className="flex h-full flex-col gap-6 p-6 md:p-8">
      {invitesQuery.isPending ? (
        <InvitesSkeleton />
      ) : invitesQuery.isError ? (
        <ErrorState message={getErrorMessage(invitesQuery.error)} />
      ) : invitesQuery.data.length === 0 ? (
        <EmptyState />
      ) : (
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Username</TableHead>
                <TableHead>Роль</TableHead>
                <TableHead>Статус</TableHead>
                <TableHead>Создан</TableHead>
                <TableHead>Истекает</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {invitesQuery.data.map((invite) => (
                <TableRow key={invite.id}>
                  <TableCell className="font-medium">
                    {invite.username}
                  </TableCell>
                  <TableCell>
                    <Badge
                      variant={invite.is_admin ? 'default' : 'secondary'}
                    >
                      {invite.is_admin ? 'Админ' : 'Пользователь'}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <Badge variant={STATUS_VARIANT[invite.status]}>
                      {STATUS_LABEL[invite.status]}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {formatDate(invite.created_at)}
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {formatDate(invite.expires_at)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}

function InvitesSkeleton() {
  return (
    <div className="rounded-md border">
      <div className="border-b p-4">
        <Skeleton className="h-5 w-40" />
      </div>
      <div className="space-y-3 p-4">
        {Array.from({ length: 5 }).map((_, idx) => (
          <Skeleton key={idx} className="h-10 w-full" />
        ))}
      </div>
    </div>
  );
}

function ErrorState({ message }: { message: string }) {
  return (
    <div className="rounded-md border border-destructive/50 bg-destructive/5 p-6">
      <p className="text-sm font-medium text-destructive">
        Не удалось загрузить инвайты
      </p>
      <p className="mt-1 text-sm text-muted-foreground">{message}</p>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="rounded-md border p-8 text-center text-sm text-muted-foreground">
      Инвайтов пока нет.
    </div>
  );
}

export default InvitesPage;
