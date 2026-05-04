import { api } from '@/lib/api';

export type ReportStatus = 'pending' | 'in_progress' | 'done' | 'error';

export interface Report {
  id: number;
  location_id: number | null;
  season_year: number;
  status: ReportStatus;
  file_size_bytes: number | null;
  error: string | null;
  created_at: string;
  finished_at: string | null;
}

export interface ReportGenerateInput {
  location_id: number;
  season_year: number;
}

export async function listReports(): Promise<Report[]> {
  const response = await api.get<Report[]>('/reports');
  return response.data;
}

export async function getReport(fileId: number): Promise<Report> {
  const response = await api.get<Report>(`/reports/${fileId}`);
  return response.data;
}

export async function generateReport(
  input: ReportGenerateInput,
): Promise<Report> {
  const response = await api.post<Report>('/reports/generate', input);
  return response.data;
}

export async function deleteReport(fileId: number): Promise<void> {
  await api.delete(`/reports/${fileId}`);
}

export async function downloadReport(fileId: number): Promise<void> {
  const response = await api.get(`/reports/${fileId}/download`, {
    responseType: 'blob',
  });
  const blob = new Blob([response.data as Blob], { type: 'application/pdf' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `report_${fileId}.pdf`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
