import { api } from '@/lib/api';
import type { WeatherSource } from '@/lib/weather-api';

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
