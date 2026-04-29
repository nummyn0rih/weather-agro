import { api } from '@/lib/api';

interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface LoginInput {
  username: string;
  password: string;
}

export async function login(input: LoginInput): Promise<TokenPair> {
  const response = await api.post<TokenPair>('/auth/login', input);
  return response.data;
}

export async function logout(): Promise<void> {
  try {
    await api.post('/auth/logout');
  } catch {
    // Stateless logout — ignore network/auth errors, frontend still clears tokens.
  }
}
