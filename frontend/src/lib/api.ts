import axios, {
  type AxiosError,
  type AxiosRequestConfig,
  type InternalAxiosRequestConfig,
} from 'axios';

import { tokenStorage } from '@/lib/auth-tokens';

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api';

export const api = axios.create({
  baseURL: API_URL,
  headers: { 'Content-Type': 'application/json' },
});

type RetryConfig = InternalAxiosRequestConfig & { _retry?: boolean };

api.interceptors.request.use((config) => {
  const token = tokenStorage.getAccess();
  if (token) {
    config.headers.set('Authorization', `Bearer ${token}`);
  }
  return config;
});

let refreshPromise: Promise<string> | null = null;

async function refreshAccessToken(): Promise<string> {
  const refreshToken = tokenStorage.getRefresh();
  if (!refreshToken) {
    throw new Error('No refresh token');
  }
  const response = await axios.post<{ access_token: string }>(
    `${API_URL}/auth/refresh`,
    { refresh_token: refreshToken },
    { headers: { 'Content-Type': 'application/json' } },
  );
  const accessToken = response.data.access_token;
  tokenStorage.setTokens(accessToken, refreshToken);
  return accessToken;
}

function redirectToLogin(): void {
  tokenStorage.clear();
  if (typeof window !== 'undefined' && window.location.pathname !== '/login') {
    window.location.assign('/login');
  }
}

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as RetryConfig | undefined;
    const status = error.response?.status;

    if (status !== 401 || !originalRequest) {
      return Promise.reject(error);
    }

    const isRefreshCall = originalRequest.url?.includes('/auth/refresh');
    if (isRefreshCall || originalRequest._retry) {
      redirectToLogin();
      return Promise.reject(error);
    }

    if (!tokenStorage.getRefresh()) {
      redirectToLogin();
      return Promise.reject(error);
    }

    originalRequest._retry = true;
    try {
      refreshPromise ??= refreshAccessToken().finally(() => {
        refreshPromise = null;
      });
      const newAccessToken = await refreshPromise;
      originalRequest.headers.set('Authorization', `Bearer ${newAccessToken}`);
      return api.request(originalRequest as AxiosRequestConfig);
    } catch (refreshError) {
      redirectToLogin();
      return Promise.reject(
        refreshError instanceof Error
          ? refreshError
          : new Error('Token refresh failed'),
      );
    }
  },
);
