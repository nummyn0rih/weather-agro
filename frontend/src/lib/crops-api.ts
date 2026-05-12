import { api } from '@/lib/api';

export interface Crop {
  id: number;
  name: string;
  base_temperature: number;
  optimal_temp_min: number | null;
  optimal_temp_max: number | null;
}

export interface CropCreate {
  name: string;
  base_temperature: number;
  optimal_temp_min?: number | null;
  optimal_temp_max?: number | null;
}

export interface CropUpdate {
  name?: string;
  base_temperature?: number;
  optimal_temp_min?: number | null;
  optimal_temp_max?: number | null;
}

export async function listCrops(): Promise<Crop[]> {
  const response = await api.get<Crop[]>('/crops');
  return response.data;
}

export async function createCrop(input: CropCreate): Promise<Crop> {
  const r = await api.post<Crop>('/crops', input);
  return r.data;
}

export async function updateCrop(id: number, input: CropUpdate): Promise<Crop> {
  const r = await api.put<Crop>(`/crops/${id}`, input);
  return r.data;
}

export async function deleteCrop(id: number): Promise<void> {
  await api.delete(`/crops/${id}`);
}
