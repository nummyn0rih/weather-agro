import { create } from 'zustand';

import { api } from '@/lib/api';
import { tokenStorage } from '@/lib/auth-tokens';

export interface UserMe {
  id: number;
  username: string;
  is_admin: boolean;
  is_active: boolean;
  telegram_chat_id: string | null;
  created_at: string;
}

interface AuthState {
  username: string | null;
  userId: number | null;
  isAdmin: boolean;
  isActive: boolean;
  isAuthenticated: boolean;
  bootstrapping: boolean;
  setSession: (
    username: string,
    accessToken: string,
    refreshToken: string,
  ) => Promise<void>;
  refreshUserInfo: () => Promise<void>;
  bootstrap: () => Promise<void>;
  clearSession: () => void;
}

const USERNAME_KEY = 'weather_agro.username';

export class AccountDeactivatedError extends Error {
  constructor() {
    super('Account is deactivated');
    this.name = 'AccountDeactivatedError';
  }
}

function readInitialUsername(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem(USERNAME_KEY);
}

function readInitialAuth(): boolean {
  return tokenStorage.getAccess() !== null;
}

async function fetchMe(): Promise<UserMe> {
  const response = await api.get<UserMe>('/auth/me');
  return response.data;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  username: readInitialUsername(),
  userId: null,
  isAdmin: false,
  isActive: false,
  isAuthenticated: readInitialAuth(),
  bootstrapping: false,
  setSession: async (username, accessToken, refreshToken) => {
    tokenStorage.setTokens(accessToken, refreshToken);
    localStorage.setItem(USERNAME_KEY, username);
    set({ username, isAuthenticated: true });
    try {
      const me = await fetchMe();
      if (!me.is_active) {
        get().clearSession();
        throw new AccountDeactivatedError();
      }
      set({
        username: me.username,
        userId: me.id,
        isAdmin: me.is_admin,
        isActive: me.is_active,
      });
      localStorage.setItem(USERNAME_KEY, me.username);
    } catch (error) {
      if (error instanceof AccountDeactivatedError) {
        throw error;
      }
      get().clearSession();
      throw error;
    }
  },
  refreshUserInfo: async () => {
    const me = await fetchMe();
    set({
      username: me.username,
      userId: me.id,
      isAdmin: me.is_admin,
      isActive: me.is_active,
    });
    localStorage.setItem(USERNAME_KEY, me.username);
  },
  bootstrap: async () => {
    if (!tokenStorage.getAccess()) {
      return;
    }
    set({ bootstrapping: true, isAuthenticated: true });
    try {
      const me = await fetchMe();
      if (!me.is_active) {
        get().clearSession();
        return;
      }
      set({
        username: me.username,
        userId: me.id,
        isAdmin: me.is_admin,
        isActive: me.is_active,
      });
      localStorage.setItem(USERNAME_KEY, me.username);
    } catch {
      get().clearSession();
    } finally {
      set({ bootstrapping: false });
    }
  },
  clearSession: () => {
    tokenStorage.clear();
    localStorage.removeItem(USERNAME_KEY);
    set({
      username: null,
      userId: null,
      isAdmin: false,
      isActive: false,
      isAuthenticated: false,
      bootstrapping: false,
    });
  },
}));
