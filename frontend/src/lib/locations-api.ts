import { api } from '@/lib/api';

export type LocationType = 'own' | 'purchase';
export type ImportStatus = 'pending' | 'in_progress' | 'done' | 'error';

export interface Location {
  id: number;
  name: string;
  latitude: number;
  longitude: number;
  region: string | null;
  type: LocationType;
  note: string | null;
  created_at: string;
  import_status: ImportStatus;
  import_progress: number;
}

export interface LocationCreateInput {
  name: string;
  latitude: number;
  longitude: number;
  region: string | null;
  type: LocationType;
  note: string | null;
}

export type LocationUpdateInput = Partial<LocationCreateInput>;

export interface LocationImportStatusSnapshot {
  location_id: number;
  status: ImportStatus;
  progress: number;
  started_at: string | null;
  finished_at: string | null;
  error: string | null;
}

export interface LocationListFilters {
  region?: string;
  type?: LocationType;
}

export async function listLocations(
  filters: LocationListFilters = {},
): Promise<Location[]> {
  const response = await api.get<Location[]>('/locations', { params: filters });
  return response.data;
}

export async function createLocation(
  input: LocationCreateInput,
): Promise<Location> {
  const response = await api.post<Location>('/locations', input);
  return response.data;
}

export async function updateLocation(
  id: number,
  input: LocationUpdateInput,
): Promise<Location> {
  const response = await api.put<Location>(`/locations/${id}`, input);
  return response.data;
}

export async function deleteLocation(id: number): Promise<void> {
  await api.delete(`/locations/${id}`);
}

export async function getImportStatus(
  id: number,
): Promise<LocationImportStatusSnapshot> {
  const response = await api.get<LocationImportStatusSnapshot>(
    `/locations/${id}/import-status`,
  );
  return response.data;
}
