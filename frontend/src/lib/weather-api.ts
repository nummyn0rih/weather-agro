import { api } from '@/lib/api';

export type WeatherSource =
  | 'open_meteo'
  | 'nasa_power'
  | 'openweathermap'
  | 'average';

export type Aggregation = 'day' | 'week' | 'month' | 'season' | 'year';
export type HeatmapXAxis = 'month' | 'week' | 'doy';
export type CumulativeParameter =
  | 'precipitation'
  | 'et0'
  | 'sunshine_hours'
  | 'gdd';
export type ExportFormat = 'csv' | 'xlsx';

export const WEATHER_PARAMETERS = [
  'temp_min',
  'temp_max',
  'temp_avg',
  'soil_temp_0',
  'soil_temp_7',
  'soil_temp_28',
  'soil_temp_100',
  'dew_point',
  'frost_hours',
  'humidity_min',
  'humidity_max',
  'humidity_avg',
  'soil_moisture_0_7',
  'soil_moisture_7_28',
  'soil_moisture_28_100',
  'precipitation',
  'et0',
  'solar_radiation',
  'sunshine_hours',
  'wind_speed_avg',
  'wind_speed_max',
  'vpd',
] as const;

export type WeatherParameter = (typeof WEATHER_PARAMETERS)[number];

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
  compare_years?: number[];
}

function appendList(
  search: URLSearchParams,
  key: string,
  values: readonly (string | number)[],
): void {
  for (const v of values) {
    search.append(key, String(v));
  }
}

function buildDailyParams(params: WeatherDailyParams): URLSearchParams {
  const search = new URLSearchParams();
  appendList(search, 'location_ids', params.location_ids);
  appendList(search, 'parameters', params.parameters);
  search.set('date_from', params.date_from);
  search.set('date_to', params.date_to);
  if (params.source) search.set('source', params.source);
  if (params.aggregation) search.set('aggregation', params.aggregation);
  if (params.compare_years && params.compare_years.length > 0) {
    appendList(search, 'compare_years', params.compare_years);
  }
  return search;
}

export async function getWeatherDaily(
  params: WeatherDailyParams,
): Promise<WeatherDailyPoint[]> {
  const response = await api.get<WeatherDailyPoint[]>('/weather/daily', {
    params: buildDailyParams(params),
  });
  return response.data;
}

export interface HeatmapCell {
  location_id: number;
  parameter: string;
  source: string;
  year: number;
  x: number;
  value: number | null;
}

export interface HeatmapParams {
  location_id: number;
  parameter: string;
  date_from: string;
  date_to: string;
  source?: WeatherSource;
  axis?: HeatmapXAxis;
}

export async function getWeatherHeatmap(
  params: HeatmapParams,
): Promise<HeatmapCell[]> {
  const search = new URLSearchParams();
  search.set('location_id', String(params.location_id));
  search.set('parameter', params.parameter);
  search.set('date_from', params.date_from);
  search.set('date_to', params.date_to);
  if (params.source) search.set('source', params.source);
  if (params.axis) search.set('axis', params.axis);
  const response = await api.get<HeatmapCell[]>('/weather/heatmap', {
    params: search,
  });
  return response.data;
}

export interface CumulativePoint {
  time: string;
  location_id: number;
  source: string;
  parameter: string;
  daily: number | null;
  cumulative: number;
}

export interface CumulativeParams {
  location_ids: number[];
  parameter: CumulativeParameter;
  date_from: string;
  date_to: string;
  source?: WeatherSource;
  base_temperature?: number;
}

export async function getWeatherCumulative(
  params: CumulativeParams,
): Promise<CumulativePoint[]> {
  const search = new URLSearchParams();
  appendList(search, 'location_ids', params.location_ids);
  search.set('parameter', params.parameter);
  search.set('date_from', params.date_from);
  search.set('date_to', params.date_to);
  if (params.source) search.set('source', params.source);
  if (params.base_temperature !== undefined) {
    search.set('base_temperature', String(params.base_temperature));
  }
  const response = await api.get<CumulativePoint[]>('/weather/cumulative', {
    params: search,
  });
  return response.data;
}

export interface ExportParams {
  location_ids: number[];
  parameters: string[];
  date_from: string;
  date_to: string;
  source?: WeatherSource;
  aggregation?: Aggregation;
  format: ExportFormat;
}

export async function downloadWeatherExport(
  params: ExportParams,
): Promise<Blob> {
  const search = new URLSearchParams();
  appendList(search, 'location_ids', params.location_ids);
  appendList(search, 'parameters', params.parameters);
  search.set('date_from', params.date_from);
  search.set('date_to', params.date_to);
  if (params.source) search.set('source', params.source);
  if (params.aggregation) search.set('aggregation', params.aggregation);
  search.set('format', params.format);
  const response = await api.get<Blob>('/weather/export', {
    params: search,
    responseType: 'blob',
  });
  return response.data;
}
