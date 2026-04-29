import { api } from '@/lib/api';
import type { WeatherSource } from '@/lib/weather-api';

export type NormalPeriod = 'month' | 'week' | 'doy';
export type AnomalyLevel = 'none' | 'moderate' | 'extreme';

export interface CorrelationMatrix {
  parameters: string[];
  matrix: (number | null)[][];
  counts: number[][];
  n: number;
}

export interface CorrelationParams {
  location_id: number;
  parameters: string[];
  date_from: string;
  date_to: string;
  source?: WeatherSource;
}

export async function getCorrelations(
  params: CorrelationParams,
): Promise<CorrelationMatrix> {
  const search = new URLSearchParams();
  search.set('location_id', String(params.location_id));
  for (const p of params.parameters) {
    search.append('parameters', p);
  }
  search.set('date_from', params.date_from);
  search.set('date_to', params.date_to);
  if (params.source) search.set('source', params.source);
  const response = await api.get<CorrelationMatrix>('/analytics/correlations', {
    params: search,
  });
  return response.data;
}

export interface ClimateNormalRow {
  location_id: number;
  parameter: string;
  period: NormalPeriod;
  bucket: number;
  mean: number | null;
  std: number | null;
  min: number | null;
  max: number | null;
  count: number;
  year_from: number | null;
  year_to: number | null;
  updated_at: string | null;
}

export interface NormalsParams {
  location_id: number;
  parameter: string;
  period?: NormalPeriod;
  refresh?: boolean;
}

export async function getClimateNormals(
  params: NormalsParams,
): Promise<ClimateNormalRow[]> {
  const search = new URLSearchParams();
  search.set('location_id', String(params.location_id));
  search.set('parameter', params.parameter);
  if (params.period) search.set('period', params.period);
  if (params.refresh) search.set('refresh', 'true');
  const response = await api.get<ClimateNormalRow[]>('/analytics/normals', {
    params: search,
  });
  return response.data;
}

export interface AnomalyRow {
  time: string;
  location_id: number;
  parameter: string;
  value: number | null;
  normal_mean: number | null;
  normal_std: number | null;
  deviation: number | null;
  sigma: number | null;
  level: AnomalyLevel;
  bucket: number;
  period: NormalPeriod;
}

export interface AnomaliesParams {
  location_id: number;
  parameter: string;
  date_from: string;
  date_to: string;
  period?: NormalPeriod;
  source?: WeatherSource;
}

export async function getAnomalies(
  params: AnomaliesParams,
): Promise<AnomalyRow[]> {
  const search = new URLSearchParams();
  search.set('location_id', String(params.location_id));
  search.set('parameter', params.parameter);
  search.set('date_from', params.date_from);
  search.set('date_to', params.date_to);
  if (params.period) search.set('period', params.period);
  if (params.source) search.set('source', params.source);
  const response = await api.get<AnomalyRow[]>('/analytics/anomalies', {
    params: search,
  });
  return response.data;
}
