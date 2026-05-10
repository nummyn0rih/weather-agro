import { api } from '@/lib/api';

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface LoginInput {
  username: string;
  password: string;
}

export interface InvitePublic {
  username: string;
  is_admin: boolean;
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

export async function getInvite(token: string): Promise<InvitePublic> {
  const response = await api.get<InvitePublic>(
    `/auth/invites/${encodeURIComponent(token)}`,
  );
  return response.data;
}

export async function acceptInvite(
  token: string,
  password: string,
): Promise<TokenPair> {
  const response = await api.post<TokenPair>(
    `/auth/invites/${encodeURIComponent(token)}/accept`,
    { password },
  );
  return response.data;
}
