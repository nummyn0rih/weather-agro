import { zodResolver } from '@hookform/resolvers/zod';
import { useMutation, useQuery } from '@tanstack/react-query';
import { isAxiosError } from 'axios';
import { useForm } from 'react-hook-form';
import { Link, Navigate, useNavigate, useParams } from 'react-router-dom';
import { toast } from 'sonner';
import { z } from 'zod';

import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import {
  acceptInvite,
  getInvite,
  type InvitePublic,
  type TokenPair,
} from '@/lib/auth-api';
import { useAuthStore } from '@/stores/auth';

const formSchema = z
  .object({
    password: z.string().min(8, 'Минимум 8 символов'),
    passwordConfirm: z.string(),
  })
  .refine((data) => data.password === data.passwordConfirm, {
    path: ['passwordConfirm'],
    message: 'Пароли не совпадают',
  });

type FormValues = z.infer<typeof formSchema>;

const INVITE_INVALID_MESSAGE =
  'Инвайт недействителен, истёк или уже использован';

export function AcceptInvitePage() {
  const { token } = useParams<{ token: string }>();
  const navigate = useNavigate();
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const setSession = useAuthStore((state) => state.setSession);

  const inviteQuery = useQuery<InvitePublic, unknown>({
    queryKey: ['invite', token],
    queryFn: () => getInvite(token as string),
    enabled: Boolean(token),
    retry: false,
    staleTime: 0,
  });

  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: { password: '', passwordConfirm: '' },
    mode: 'onTouched',
  });

  const acceptMutation = useMutation<TokenPair, unknown, { password: string }>({
    mutationFn: async ({ password }) => acceptInvite(token as string, password),
    onSuccess: async (tokens) => {
      const username = inviteQuery.data?.username ?? '';
      try {
        await setSession(username, tokens.access_token, tokens.refresh_token);
        toast.success('Аккаунт создан');
        void navigate('/', { replace: true });
      } catch (error) {
        toast.error(extractErrorMessage(error));
      }
    },
    onError: (error) => {
      toast.error(extractErrorMessage(error));
    },
  });

  if (isAuthenticated && !acceptMutation.isPending && !acceptMutation.isError) {
    return <Navigate to="/" replace />;
  }

  if (!token) {
    return <InviteErrorCard message={INVITE_INVALID_MESSAGE} />;
  }

  if (inviteQuery.isPending) {
    return <InviteLoadingCard />;
  }

  if (inviteQuery.isError) {
    const status = isAxiosError(inviteQuery.error)
      ? inviteQuery.error.response?.status
      : undefined;
    const message =
      status === 404 || status === 410
        ? INVITE_INVALID_MESSAGE
        : (extractErrorMessage(inviteQuery.error) ?? INVITE_INVALID_MESSAGE);
    return <InviteErrorCard message={message} />;
  }

  const invite = inviteQuery.data;

  const onSubmit = (values: FormValues) => {
    acceptMutation.mutate({ password: values.password });
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-4">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>Создание аккаунта</CardTitle>
          <CardDescription>
            Задайте пароль, чтобы завершить регистрацию.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="rounded-md border bg-muted/40 p-3 text-sm">
            <div className="text-muted-foreground">Email</div>
            <div className="font-medium break-all">{invite.username}</div>
            <div className="mt-2 text-muted-foreground">Роль</div>
            <div className="font-medium">
              {invite.is_admin ? 'Администратор' : 'Пользователь'}
            </div>
          </div>
          <Form {...form}>
            <form
              className="space-y-4"
              onSubmit={form.handleSubmit(onSubmit)}
              noValidate
            >
              <FormField
                control={form.control}
                name="password"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Пароль</FormLabel>
                    <FormControl>
                      <Input
                        type="password"
                        autoComplete="new-password"
                        disabled={acceptMutation.isPending}
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="passwordConfirm"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Повторите пароль</FormLabel>
                    <FormControl>
                      <Input
                        type="password"
                        autoComplete="new-password"
                        disabled={acceptMutation.isPending}
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <Button
                type="submit"
                className="w-full"
                disabled={acceptMutation.isPending}
              >
                {acceptMutation.isPending ? 'Создание…' : 'Создать аккаунт'}
              </Button>
            </form>
          </Form>
        </CardContent>
      </Card>
    </div>
  );
}

function InviteLoadingCard() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-4">
      <Card className="w-full max-w-sm">
        <CardHeader className="space-y-2">
          <Skeleton className="h-6 w-2/3" />
          <Skeleton className="h-4 w-3/4" />
        </CardHeader>
        <CardContent className="space-y-4">
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
        </CardContent>
      </Card>
    </div>
  );
}

function InviteErrorCard({ message }: { message: string }) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-4">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>Инвайт недоступен</CardTitle>
          <CardDescription>{message}</CardDescription>
        </CardHeader>
        <CardContent>
          <Button asChild className="w-full">
            <Link to="/">На главную</Link>
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}

function extractErrorMessage(error: unknown): string {
  if (isAxiosError(error)) {
    const status = error.response?.status;
    if (status === 404 || status === 410) return INVITE_INVALID_MESSAGE;
    if (status === 429) return 'Слишком много попыток. Попробуйте позже.';
    const detail = (error.response?.data as { detail?: unknown } | undefined)
      ?.detail;
    if (typeof detail === 'string') return detail;
    return 'Не удалось завершить регистрацию.';
  }
  if (error instanceof Error) return error.message;
  return 'Неизвестная ошибка.';
}

export default AcceptInvitePage;
