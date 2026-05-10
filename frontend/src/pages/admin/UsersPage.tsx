import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import axios from 'axios';
import { Copy, MoreHorizontal, RefreshCw } from 'lucide-react';
import { useState } from 'react';
import { toast } from 'sonner';

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
import { Badge } from '@/components/ui/badge';
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
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  type AdminUser,
  listUsers,
  resetUserPassword,
  updateUser,
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

const PASSWORD_ALPHABET =
  'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';

function generatePassword(length = 16): string {
  const buf = new Uint32Array(length);
  crypto.getRandomValues(buf);
  let out = '';
  for (let i = 0; i < length; i += 1) {
    out += PASSWORD_ALPHABET[buf[i]! % PASSWORD_ALPHABET.length];
  }
  return out;
}

interface DeactivateState {
  user: AdminUser;
}

interface ResetPasswordState {
  user: AdminUser;
  password: string;
}

export function UsersPage() {
  const queryClient = useQueryClient();

  const usersQuery = useQuery({
    queryKey: ['admin', 'users'],
    queryFn: listUsers,
  });

  const [deactivateTarget, setDeactivateTarget] =
    useState<DeactivateState | null>(null);
  const [resetTarget, setResetTarget] = useState<ResetPasswordState | null>(
    null,
  );

  const updateMutation = useMutation({
    mutationFn: (vars: {
      id: number;
      input: { is_admin?: boolean; is_active?: boolean };
    }) => updateUser(vars.id, vars.input),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['admin', 'users'] });
    },
    onError: (error) => {
      toast.error(getErrorMessage(error));
    },
  });

  const resetMutation = useMutation({
    mutationFn: (vars: { id: number; password: string }) =>
      resetUserPassword(vars.id, vars.password),
    onSuccess: () => {
      toast.success('Пароль сброшен');
      void queryClient.invalidateQueries({ queryKey: ['admin', 'users'] });
      setResetTarget(null);
    },
    onError: (error) => {
      toast.error(getErrorMessage(error));
    },
  });

  const handleToggleAdmin = (user: AdminUser) => {
    updateMutation.mutate({
      id: user.id,
      input: { is_admin: !user.is_admin },
    });
  };

  const handleActivate = (user: AdminUser) => {
    updateMutation.mutate({
      id: user.id,
      input: { is_active: true },
    });
  };

  const handleConfirmDeactivate = () => {
    if (!deactivateTarget) return;
    updateMutation.mutate(
      {
        id: deactivateTarget.user.id,
        input: { is_active: false },
      },
      {
        onSettled: () => {
          setDeactivateTarget(null);
        },
      },
    );
  };

  const handleOpenReset = (user: AdminUser) => {
    setResetTarget({ user, password: generatePassword() });
  };

  const handleCopyPassword = async () => {
    if (!resetTarget) return;
    try {
      await navigator.clipboard.writeText(resetTarget.password);
      toast.success('Скопировано');
    } catch {
      toast.error('Не удалось скопировать');
    }
  };

  const handleSubmitReset = () => {
    if (!resetTarget) return;
    if (resetTarget.password.length < 8) {
      toast.error('Пароль должен быть не короче 8 символов');
      return;
    }
    resetMutation.mutate({
      id: resetTarget.user.id,
      password: resetTarget.password,
    });
  };

  return (
    <div className="flex h-full flex-col gap-6 p-6 md:p-8">
      {usersQuery.isPending ? (
        <UsersSkeleton />
      ) : usersQuery.isError ? (
        <ErrorState message={getErrorMessage(usersQuery.error)} />
      ) : usersQuery.data.length === 0 ? (
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
                <TableHead className="w-[60px]" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {usersQuery.data.map((user) => (
                <TableRow key={user.id}>
                  <TableCell className="font-medium">{user.username}</TableCell>
                  <TableCell>
                    <Badge
                      variant={user.is_admin ? 'default' : 'secondary'}
                    >
                      {user.is_admin ? 'Админ' : 'Пользователь'}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <Badge
                      variant={user.is_active ? 'secondary' : 'destructive'}
                    >
                      {user.is_active ? 'Активен' : 'Деактивирован'}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {formatDate(user.created_at)}
                  </TableCell>
                  <TableCell>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button
                          variant="ghost"
                          size="icon"
                          aria-label="Действия"
                          disabled={updateMutation.isPending}
                        >
                          <MoreHorizontal className="h-4 w-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem
                          onSelect={() => handleToggleAdmin(user)}
                        >
                          {user.is_admin ? 'Снять админа' : 'Сделать админом'}
                        </DropdownMenuItem>
                        {user.is_active ? (
                          <DropdownMenuItem
                            onSelect={() =>
                              setDeactivateTarget({ user })
                            }
                          >
                            Деактивировать
                          </DropdownMenuItem>
                        ) : (
                          <DropdownMenuItem
                            onSelect={() => handleActivate(user)}
                          >
                            Активировать
                          </DropdownMenuItem>
                        )}
                        <DropdownMenuSeparator />
                        <DropdownMenuItem
                          onSelect={() => handleOpenReset(user)}
                        >
                          Сбросить пароль
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      <AlertDialog
        open={deactivateTarget !== null}
        onOpenChange={(open) => {
          if (!open) setDeactivateTarget(null);
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Деактивировать пользователя?</AlertDialogTitle>
            <AlertDialogDescription>
              {deactivateTarget
                ? `Пользователь ${deactivateTarget.user.username} не сможет войти, пока вы не активируете его снова.`
                : ''}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Отмена</AlertDialogCancel>
            <AlertDialogAction
              onClick={(event) => {
                event.preventDefault();
                handleConfirmDeactivate();
              }}
              disabled={updateMutation.isPending}
            >
              Деактивировать
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <Dialog
        open={resetTarget !== null}
        onOpenChange={(open) => {
          if (!open) setResetTarget(null);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Сброс пароля</DialogTitle>
            <DialogDescription>
              {resetTarget
                ? `Новый пароль для ${resetTarget.user.username}. Сохраните его до отправки — после закрытия окна восстановить нельзя.`
                : ''}
            </DialogDescription>
          </DialogHeader>
          {resetTarget && (
            <div className="space-y-3">
              <div className="space-y-2">
                <Label htmlFor="admin-reset-password">Пароль (≥8 символов)</Label>
                <div className="flex gap-2">
                  <Input
                    id="admin-reset-password"
                    type="text"
                    autoComplete="off"
                    spellCheck={false}
                    value={resetTarget.password}
                    onChange={(event) =>
                      setResetTarget({
                        ...resetTarget,
                        password: event.target.value,
                      })
                    }
                  />
                  <Button
                    type="button"
                    variant="outline"
                    size="icon"
                    onClick={() =>
                      setResetTarget({
                        ...resetTarget,
                        password: generatePassword(),
                      })
                    }
                    aria-label="Сгенерировать"
                  >
                    <RefreshCw className="h-4 w-4" />
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    size="icon"
                    onClick={() => {
                      void handleCopyPassword();
                    }}
                    aria-label="Скопировать"
                  >
                    <Copy className="h-4 w-4" />
                  </Button>
                </div>
              </div>
              <p className="text-xs text-muted-foreground">
                После сохранения пароль не отображается повторно. Передайте его
                пользователю по защищённому каналу.
              </p>
            </div>
          )}
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setResetTarget(null)}
              disabled={resetMutation.isPending}
            >
              Отмена
            </Button>
            <Button
              onClick={handleSubmitReset}
              disabled={
                resetMutation.isPending ||
                !resetTarget ||
                resetTarget.password.length < 8
              }
            >
              Сбросить
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function UsersSkeleton() {
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
        Не удалось загрузить пользователей
      </p>
      <p className="mt-1 text-sm text-muted-foreground">{message}</p>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="rounded-md border p-8 text-center text-sm text-muted-foreground">
      Пользователей пока нет.
    </div>
  );
}

export default UsersPage;
