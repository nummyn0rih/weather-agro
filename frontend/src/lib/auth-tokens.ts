const ACCESS_KEY = 'weather_agro.access_token';
const REFRESH_KEY = 'weather_agro.refresh_token';

export const tokenStorage = {
  getAccess(): string | null {
    return localStorage.getItem(ACCESS_KEY);
  },
  getRefresh(): string | null {
    return localStorage.getItem(REFRESH_KEY);
  },
  setTokens(access: string, refresh?: string): void {
    localStorage.setItem(ACCESS_KEY, access);
    if (refresh !== undefined) {
      localStorage.setItem(REFRESH_KEY, refresh);
    }
  },
  clear(): void {
    localStorage.removeItem(ACCESS_KEY);
    localStorage.removeItem(REFRESH_KEY);
  },
};
