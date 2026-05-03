import { api } from '@/lib/api';

export type EventType = 'planting' | 'harvest' | 'note';

export interface EventWeather {
  temp_min: number | null;
  temp_max: number | null;
  temp_avg: number | null;
  soil_temp_0: number | null;
  soil_temp_7: number | null;
  soil_temp_28: number | null;
  soil_temp_100: number | null;
  dew_point: number | null;
  frost_hours: number | null;
  humidity_min: number | null;
  humidity_max: number | null;
  humidity_avg: number | null;
  soil_moisture_0_7: number | null;
  soil_moisture_7_28: number | null;
  soil_moisture_28_100: number | null;
  precipitation: number | null;
  et0: number | null;
  solar_radiation: number | null;
  sunshine_hours: number | null;
  wind_speed_avg: number | null;
  wind_speed_max: number | null;
  vpd: number | null;
}

export interface FieldEvent {
  id: number;
  location_id: number;
  event_type: EventType;
  event_date: string;
  crop_id: number | null;
  variety: string | null;
  area_hectares: number | null;
  yield_kg: number | null;
  quality_rating: number | null;
  description: string | null;
  photos: string[];
  created_at: string;
  weather: EventWeather | null;
}

export interface FieldEventCreateInput {
  location_id: number;
  event_type: EventType;
  event_date: string;
  crop_id: number | null;
  variety: string | null;
  area_hectares: number | null;
  yield_kg: number | null;
  quality_rating: number | null;
  description: string | null;
}

export type FieldEventUpdateInput = Partial<FieldEventCreateInput>;

export interface FieldEventListFilters {
  location_id?: number;
  event_type?: EventType;
  crop_id?: number;
  date_from?: string;
  date_to?: string;
}

export async function listEvents(
  filters: FieldEventListFilters = {},
): Promise<FieldEvent[]> {
  const response = await api.get<FieldEvent[]>('/events', { params: filters });
  return response.data;
}

export async function getEvent(id: number): Promise<FieldEvent> {
  const response = await api.get<FieldEvent>(`/events/${id}`);
  return response.data;
}

export async function createEvent(
  input: FieldEventCreateInput,
): Promise<FieldEvent> {
  const response = await api.post<FieldEvent>('/events', input);
  return response.data;
}

export async function updateEvent(
  id: number,
  input: FieldEventUpdateInput,
): Promise<FieldEvent> {
  const response = await api.put<FieldEvent>(`/events/${id}`, input);
  return response.data;
}

export async function deleteEvent(id: number): Promise<void> {
  await api.delete(`/events/${id}`);
}

export async function uploadPhotos(
  id: number,
  files: File[],
): Promise<FieldEvent> {
  const form = new FormData();
  for (const file of files) {
    form.append('files', file);
  }
  const response = await api.post<FieldEvent>(`/events/${id}/photos`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return response.data;
}

export async function deletePhoto(
  id: number,
  filename: string,
): Promise<FieldEvent> {
  const response = await api.delete<FieldEvent>(
    `/events/${id}/photos/${encodeURIComponent(filename)}`,
  );
  return response.data;
}

export function photoSrc(path: string): string {
  if (/^https?:/.test(path)) return path;
  const base = api.defaults.baseURL ?? '';
  try {
    const url = new URL(base);
    return `${url.origin}${path}`;
  } catch {
    return path;
  }
}

export function photoFilename(path: string): string {
  const idx = path.lastIndexOf('/');
  return idx === -1 ? path : path.slice(idx + 1);
}
