import { api } from '@/lib/api';

export interface Crop {
  id: number;
  name: string;
  base_temperature: number;
  optimal_temp_min: number | null;
  optimal_temp_max: number | null;
}

export async function listCrops(): Promise<Crop[]> {
  const response = await api.get<Crop[]>('/crops');
  return response.data;
}
