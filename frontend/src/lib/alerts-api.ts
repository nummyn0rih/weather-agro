import { api } from '@/lib/api';

export type AlertParameter =
  | 'temperature_avg'
  | 'temperature_min'
  | 'temperature_max'
  | 'precipitation'
  | 'humidity_avg'
  | 'wind_speed_avg'
  | 'wind_speed_max'
  | 'pressure_avg'
  | 'vpd_avg'
  | 'soil_moisture_avg'
  | 'soil_temperature_avg';

export type AlertCondition = 'gt' | 'lt' | 'eq' | 'between';

export interface AlertRule {
  id: number;
  name: string;
  parameter: AlertParameter;
  condition: AlertCondition;
  threshold: number;
  threshold_max: number | null;
  location_ids: number[];
  enabled: boolean;
  telegram: boolean;
  created_at: string;
}

export interface AlertRuleCreateInput {
  name: string;
  parameter: AlertParameter;
  condition: AlertCondition;
  threshold: number;
  threshold_max: number | null;
  location_ids: number[];
  enabled: boolean;
  telegram: boolean;
}

export type AlertRuleUpdateInput = Partial<AlertRuleCreateInput>;

export interface AlertHistoryItem {
  id: number;
  rule_id: number | null;
  rule_name: string;
  location_id: number | null;
  location_name: string;
  parameter: string;
  condition: string;
  threshold: number;
  threshold_max: number | null;
  value: number;
  triggered_at: string;
  message: string;
}

export interface AlertHistoryResponse {
  items: AlertHistoryItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface AlertHistoryFilters {
  location_id?: number;
  rule_id?: number;
  date_from?: string;
  date_to?: string;
  limit?: number;
  offset?: number;
}

export interface TelegramBindCode {
  code: string;
  expires_at: string;
  bot_username: string | null;
}

export interface TelegramBindStatus {
  chat_id: number | null;
  bound: boolean;
}

export async function listRules(enabled?: boolean): Promise<AlertRule[]> {
  const params: Record<string, boolean> = {};
  if (enabled !== undefined) params.enabled = enabled;
  const response = await api.get<AlertRule[]>('/alerts/rules', { params });
  return response.data;
}

export async function createRule(
  input: AlertRuleCreateInput,
): Promise<AlertRule> {
  const response = await api.post<AlertRule>('/alerts/rules', input);
  return response.data;
}

export async function updateRule(
  id: number,
  input: AlertRuleUpdateInput,
): Promise<AlertRule> {
  const response = await api.put<AlertRule>(`/alerts/rules/${id}`, input);
  return response.data;
}

export async function deleteRule(id: number): Promise<void> {
  await api.delete(`/alerts/rules/${id}`);
}

export async function listHistory(
  filters: AlertHistoryFilters = {},
): Promise<AlertHistoryResponse> {
  const response = await api.get<AlertHistoryResponse>('/alerts/history', {
    params: filters,
  });
  return response.data;
}

export async function issueTelegramBindCode(): Promise<TelegramBindCode> {
  const response = await api.post<TelegramBindCode>('/auth/telegram/bind-code');
  return response.data;
}

export async function getTelegramStatus(): Promise<TelegramBindStatus> {
  const response = await api.get<TelegramBindStatus>('/auth/telegram/status');
  return response.data;
}

export async function unbindTelegram(): Promise<void> {
  await api.delete('/auth/telegram/bind');
}
