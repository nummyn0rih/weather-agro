import { useMutation } from '@tanstack/react-query';
import { isAxiosError } from 'axios';
import { useState, type FormEvent } from 'react';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';

import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { login as loginRequest } from '@/lib/auth-api';
import { useAuthStore } from '@/stores/auth';

interface LocationState {
  from?: { pathname: string };
}

export function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const setSession = useAuthStore((state) => state.setSession);

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');

  const mutation = useMutation({
    mutationFn: loginRequest,
    onSuccess: (data, variables) => {
      setSession(variables.username, data.access_token, data.refresh_token);
      const redirectTo =
        (location.state as LocationState | null)?.from?.pathname ?? '/';
      void navigate(redirectTo, { replace: true });
    },
  });

  if (isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!username || !password || mutation.isPending) return;
    mutation.mutate({ username, password });
  };

  const errorMessage = mutation.isError
    ? extractErrorMessage(mutation.error)
    : null;

  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-4">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>Вход в Weather Agro</CardTitle>
          <CardDescription>
            Введите учётные данные администратора.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form className="space-y-4" onSubmit={handleSubmit} noValidate>
            <div className="space-y-2">
              <Label htmlFor="username">Логин</Label>
              <Input
                id="username"
                name="username"
                type="text"
                autoComplete="username"
                required
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                disabled={mutation.isPending}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Пароль</Label>
              <Input
                id="password"
                name="password"
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={mutation.isPending}
              />
            </div>
            {errorMessage && (
              <p
                className="text-sm text-destructive"
                role="alert"
                aria-live="polite"
              >
                {errorMessage}
              </p>
            )}
            <Button
              type="submit"
              className="w-full"
              disabled={mutation.isPending || !username || !password}
            >
              {mutation.isPending ? 'Вход…' : 'Войти'}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}

function extractErrorMessage(error: unknown): string {
  if (isAxiosError(error)) {
    const status = error.response?.status;
    if (status === 401) return 'Неверный логин или пароль.';
    if (status === 429) return 'Слишком много попыток. Попробуйте позже.';
    const detail = (error.response?.data as { detail?: unknown } | undefined)
      ?.detail;
    if (typeof detail === 'string') return detail;
    return 'Не удалось войти. Проверьте подключение к серверу.';
  }
  if (error instanceof Error) return error.message;
  return 'Неизвестная ошибка.';
}

export default LoginPage;
