import { api } from '@/lib/api';

export type SourceName = 'open_meteo' | 'nasa_power' | 'openweathermap';

export interface SourcesSettings {
  priority: SourceName[];
  enabled: Record<SourceName, boolean>;
  average_mode: boolean;
}

export interface SourcesUpdate {
  priority?: SourceName[];
  enabled?: Record<SourceName, boolean>;
  average_mode?: boolean;
}

export interface ApiKeysSettings {
  openweathermap_api_key: string | null;
}

export interface ApiKeysUpdate {
  openweathermap_api_key?: string | null;
}

export interface TelegramSettings {
  bot_token: string | null;
}

export interface TelegramUpdate {
  bot_token?: string | null;
}

export interface BackupSettings {
  yandex_disk_login: string | null;
  yandex_disk_app_password: string | null;
  yandex_disk_path: string;
  retention_daily: number;
  retention_monthly: number;
}

export interface BackupUpdate {
  yandex_disk_login?: string | null;
  yandex_disk_app_password?: string | null;
  yandex_disk_path?: string | null;
  retention_daily?: number | null;
  retention_monthly?: number | null;
}

export async function getSources(): Promise<SourcesSettings> {
  const r = await api.get<SourcesSettings>('/settings/sources');
  return r.data;
}

export async function updateSources(
  input: SourcesUpdate,
): Promise<SourcesSettings> {
  const r = await api.put<SourcesSettings>('/settings/sources', input);
  return r.data;
}

export async function getApiKeys(): Promise<ApiKeysSettings> {
  const r = await api.get<ApiKeysSettings>('/settings/api-keys');
  return r.data;
}

export async function updateApiKeys(
  input: ApiKeysUpdate,
): Promise<ApiKeysSettings> {
  const r = await api.put<ApiKeysSettings>('/settings/api-keys', input);
  return r.data;
}

export async function getTelegram(): Promise<TelegramSettings> {
  const r = await api.get<TelegramSettings>('/settings/telegram');
  return r.data;
}

export async function updateTelegram(
  input: TelegramUpdate,
): Promise<TelegramSettings> {
  const r = await api.put<TelegramSettings>('/settings/telegram', input);
  return r.data;
}

export async function getBackup(): Promise<BackupSettings> {
  const r = await api.get<BackupSettings>('/settings/backup');
  return r.data;
}

export async function updateBackup(
  input: BackupUpdate,
): Promise<BackupSettings> {
  const r = await api.put<BackupSettings>('/settings/backup', input);
  return r.data;
}

export interface TelegramBindCode {
  code: string;
  expires_at: string;
  bot_username: string | null;
}

export interface TelegramBindStatus {
  chat_id: string | null;
  bound: boolean;
}

export async function getTelegramBindStatus(): Promise<TelegramBindStatus> {
  const r = await api.get<TelegramBindStatus>('/auth/telegram/status');
  return r.data;
}

export async function issueTelegramBindCode(): Promise<TelegramBindCode> {
  const r = await api.post<TelegramBindCode>('/auth/telegram/bind-code');
  return r.data;
}

export async function unbindTelegram(): Promise<void> {
  await api.delete('/auth/telegram/bind');
}

export async function changePassword(
  old_password: string,
  new_password: string,
): Promise<void> {
  await api.post('/auth/change-password', { old_password, new_password });
}
