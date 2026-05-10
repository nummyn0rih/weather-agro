import { api } from '@/lib/api';

export interface AdminUser {
  id: number;
  username: string;
  is_admin: boolean;
  is_active: boolean;
  created_at: string;
}

export interface AdminUserUpdateInput {
  is_admin?: boolean;
  is_active?: boolean;
}

export type InviteStatus = 'pending' | 'accepted' | 'revoked' | 'expired';

export interface AdminInvite {
  id: number;
  username: string;
  is_admin: boolean;
  created_at: string;
  expires_at: string;
  accepted_at: string | null;
  revoked_at: string | null;
  status: InviteStatus;
}

export async function listUsers(): Promise<AdminUser[]> {
  const response = await api.get<AdminUser[]>('/admin/users');
  return response.data;
}

export async function updateUser(
  id: number,
  input: AdminUserUpdateInput,
): Promise<AdminUser> {
  const response = await api.patch<AdminUser>(`/admin/users/${id}`, input);
  return response.data;
}

export async function resetUserPassword(
  id: number,
  password: string,
): Promise<AdminUser> {
  const response = await api.post<AdminUser>(
    `/admin/users/${id}/reset-password`,
    { password },
  );
  return response.data;
}

export async function listInvites(): Promise<AdminInvite[]> {
  const response = await api.get<AdminInvite[]>('/admin/invites');
  return response.data;
}

export interface InviteCreatePayload {
  username: string;
  is_admin: boolean;
}

export interface InviteCreatedResponse {
  id: number;
  token: string;
  invite_url: string;
  username: string;
  is_admin: boolean;
  expires_at: string;
}

export async function createInvite(
  payload: InviteCreatePayload,
): Promise<InviteCreatedResponse> {
  const response = await api.post<InviteCreatedResponse>(
    '/admin/invites',
    payload,
  );
  return response.data;
}

export async function revokeInvite(id: number): Promise<void> {
  await api.delete(`/admin/invites/${id}`);
}
