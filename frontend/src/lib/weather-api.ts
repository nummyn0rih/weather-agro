import { api } from '@/lib/api';

export type WeatherSource =
  | 'open_meteo'
  | 'nasa_power'
  | 'openweathermap'
  | 'average';

export type Aggregation = 'day' | 'week' | 'month' | 'season' | 'year';

export interface WeatherDailyPoint {
  time: string;
  location_id: number;
  source: string;
  [parameter: string]: string | number | null;
}

export interface WeatherDailyParams {
  location_ids: number[];
  parameters: string[];
  date_from: string;
  date_to: string;
  source?: WeatherSource;
  aggregation?: Aggregation;
}

function buildParams(params: WeatherDailyParams): URLSearchParams {
  const search = new URLSearchParams();
  for (const id of params.location_ids) {
    search.append('location_ids', String(id));
  }
  for (const p of params.parameters) {
    search.append('parameters', p);
  }
  search.set('date_from', params.date_from);
  search.set('date_to', params.date_to);
  if (params.source) search.set('source', params.source);
  if (params.aggregation) search.set('aggregation', params.aggregation);
  return search;
}

export async function getWeatherDaily(
  params: WeatherDailyParams,
): Promise<WeatherDailyPoint[]> {
  const response = await api.get<WeatherDailyPoint[]>('/weather/daily', {
    params: buildParams(params),
  });
  return response.data;
}
