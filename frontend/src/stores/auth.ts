import { create } from 'zustand';

import { tokenStorage } from '@/lib/auth-tokens';

interface AuthState {
  username: string | null;
  isAuthenticated: boolean;
  setSession: (
    username: string,
    accessToken: string,
    refreshToken: string,
  ) => void;
  clearSession: () => void;
}

const USERNAME_KEY = 'weather_agro.username';

function readInitialUsername(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem(USERNAME_KEY);
}

function readInitialAuth(): boolean {
  return tokenStorage.getAccess() !== null;
}

export const useAuthStore = create<AuthState>((set) => ({
  username: readInitialUsername(),
  isAuthenticated: readInitialAuth(),
  setSession: (username, accessToken, refreshToken) => {
    tokenStorage.setTokens(accessToken, refreshToken);
    localStorage.setItem(USERNAME_KEY, username);
    set({ username, isAuthenticated: true });
  },
  clearSession: () => {
    tokenStorage.clear();
    localStorage.removeItem(USERNAME_KEY);
    set({ username: null, isAuthenticated: false });
  },
}));
