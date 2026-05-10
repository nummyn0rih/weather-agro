import { zodResolver } from '@hookform/resolvers/zod';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import axios from 'axios';
import { Copy, Trash2 } from 'lucide-react';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { toast } from 'sonner';
import { z } from 'zod';

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { Badge, type BadgeProps } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { Switch } from '@/components/ui/switch';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  type AdminInvite,
  type InviteCreatedResponse,
  type InviteStatus,
  createInvite,
  listInvites,
  revokeInvite,
} from '@/lib/admin-api';

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

function extractErrorMessage(error: unknown): string {
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

const createSchema = z.object({
  username: z.string().email('Введите корректный email'),
  is_admin: z.boolean(),
});

type CreateFormValues = z.infer<typeof createSchema>;

function buildAcceptUrl(token: string): string {
  return `${window.location.origin}/accept-invite/${token}`;
}

export function InvitesPage() {
  const queryClient = useQueryClient();

  const invitesQuery = useQuery({
    queryKey: ['admin', 'invites'],
    queryFn: listInvites,
  });

  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [createdInvite, setCreatedInvite] =
    useState<InviteCreatedResponse | null>(null);
  const [revokeTarget, setRevokeTarget] = useState<AdminInvite | null>(null);

  const handleCloseCreateDialog = () => {
    setCreateDialogOpen(false);
    setCreatedInvite(null);
  };

  const revokeMutation = useMutation({
    mutationFn: (id: number) => revokeInvite(id),
    onSuccess: () => {
      toast.success('Инвайт отозван');
      void queryClient.invalidateQueries({ queryKey: ['admin', 'invites'] });
      setRevokeTarget(null);
    },
    onError: (error) => {
      toast.error(extractErrorMessage(error));
    },
  });

  return (
    <div className="flex h-full flex-col gap-6 p-6 md:p-8">
      <div className="flex items-center justify-between gap-4">
        <h1 className="text-xl font-semibold">Инвайты</h1>
        <Button
          onClick={() => {
            setCreatedInvite(null);
            setCreateDialogOpen(true);
          }}
        >
          Создать инвайт
        </Button>
      </div>

      {invitesQuery.isPending ? (
        <InvitesSkeleton />
      ) : invitesQuery.isError ? (
        <ErrorState message={extractErrorMessage(invitesQuery.error)} />
      ) : invitesQuery.data.length === 0 ? (
        <EmptyState />
      ) : (
        <div className="overflow-x-auto rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Username</TableHead>
                <TableHead>Роль</TableHead>
                <TableHead>Статус</TableHead>
                <TableHead>Создан</TableHead>
                <TableHead>Истекает</TableHead>
                <TableHead className="w-[60px]" />
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
                  <TableCell>
                    {invite.status === 'pending' ? (
                      <Button
                        variant="ghost"
                        size="icon"
                        aria-label="Отозвать"
                        onClick={() => setRevokeTarget(invite)}
                        disabled={
                          revokeMutation.isPending &&
                          revokeTarget?.id === invite.id
                        }
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    ) : null}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      <CreateInviteDialog
        open={createDialogOpen}
        onOpenChange={(open) => {
          if (!open) handleCloseCreateDialog();
          else setCreateDialogOpen(true);
        }}
        createdInvite={createdInvite}
        onCreated={(invite) => {
          setCreatedInvite(invite);
          void queryClient.invalidateQueries({
            queryKey: ['admin', 'invites'],
          });
        }}
      />

      <AlertDialog
        open={revokeTarget !== null}
        onOpenChange={(open) => {
          if (!open && !revokeMutation.isPending) setRevokeTarget(null);
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Отозвать инвайт?</AlertDialogTitle>
            <AlertDialogDescription>
              {revokeTarget
                ? `Отозвать инвайт для ${revokeTarget.username}? Действие необратимо.`
                : ''}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={revokeMutation.isPending}>
              Отмена
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={(event) => {
                event.preventDefault();
                if (revokeTarget) revokeMutation.mutate(revokeTarget.id);
              }}
              disabled={revokeMutation.isPending}
            >
              Отозвать
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

interface CreateInviteDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  createdInvite: InviteCreatedResponse | null;
  onCreated: (invite: InviteCreatedResponse) => void;
}

function CreateInviteDialog({
  open,
  onOpenChange,
  createdInvite,
  onCreated,
}: CreateInviteDialogProps) {
  const form = useForm<CreateFormValues>({
    resolver: zodResolver(createSchema),
    defaultValues: { username: '', is_admin: false },
  });

  const createMutation = useMutation({
    mutationFn: (payload: CreateFormValues) => createInvite(payload),
    onSuccess: (data) => {
      onCreated(data);
      form.reset({ username: '', is_admin: false });
    },
    onError: (error) => {
      toast.error(extractErrorMessage(error));
    },
  });

  const handleSubmit = form.handleSubmit((values) => {
    createMutation.mutate(values);
  });

  const handleOpenChange = (next: boolean) => {
    if (createMutation.isPending) return;
    if (!next) form.reset({ username: '', is_admin: false });
    onOpenChange(next);
  };

  const acceptUrl = createdInvite ? buildAcceptUrl(createdInvite.token) : '';

  const handleCopy = async () => {
    if (!acceptUrl) return;
    try {
      await navigator.clipboard.writeText(acceptUrl);
      toast.success('Скопировано');
    } catch {
      toast.error('Не удалось скопировать');
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto">
        {createdInvite ? (
          <>
            <DialogHeader>
              <DialogTitle>Инвайт создан</DialogTitle>
              <DialogDescription>
                Передайте ссылку пользователю {createdInvite.username}.
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-3">
              <div className="flex flex-col gap-2 sm:flex-row">
                <Input
                  readOnly
                  value={acceptUrl}
                  onFocus={(event) => event.currentTarget.select()}
                  aria-label="Ссылка инвайта"
                />
                <Button
                  type="button"
                  variant="outline"
                  size="icon"
                  onClick={() => {
                    void handleCopy();
                  }}
                  aria-label="Скопировать"
                >
                  <Copy className="h-4 w-4" />
                </Button>
              </div>
              <p className="rounded-md bg-muted p-3 text-xs text-muted-foreground">
                Скопируйте ссылку — она показывается только один раз.
                Истекает {formatDate(createdInvite.expires_at)}.
              </p>
            </div>
            <DialogFooter>
              <Button onClick={() => handleOpenChange(false)}>Готово</Button>
            </DialogFooter>
          </>
        ) : (
          <>
            <DialogHeader>
              <DialogTitle>Новый инвайт</DialogTitle>
              <DialogDescription>
                Срок действия — 7 дней. Ссылка будет показана один раз.
              </DialogDescription>
            </DialogHeader>
            <Form {...form}>
              <form
                onSubmit={(event) => {
                  void handleSubmit(event);
                }}
                className="space-y-4"
              >
                <FormField
                  control={form.control}
                  name="username"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Email</FormLabel>
                      <FormControl>
                        <Input
                          type="email"
                          autoComplete="off"
                          placeholder="user@example.com"
                          {...field}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="is_admin"
                  render={({ field }) => (
                    <FormItem className="flex items-center justify-between gap-4 rounded-md border p-3">
                      <div className="space-y-1">
                        <FormLabel className="text-sm">
                          Права администратора
                        </FormLabel>
                        <FormDescription className="text-xs">
                          Полный доступ ко всем разделам.
                        </FormDescription>
                      </div>
                      <FormControl>
                        <Switch
                          checked={field.value}
                          onCheckedChange={field.onChange}
                        />
                      </FormControl>
                    </FormItem>
                  )}
                />
                <DialogFooter>
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => handleOpenChange(false)}
                    disabled={createMutation.isPending}
                  >
                    Отмена
                  </Button>
                  <Button
                    type="submit"
                    disabled={
                      createMutation.isPending || !form.formState.isValid
                    }
                  >
                    Создать
                  </Button>
                </DialogFooter>
              </form>
            </Form>
          </>
        )}
      </DialogContent>
    </Dialog>
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
