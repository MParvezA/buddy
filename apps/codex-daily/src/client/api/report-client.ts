import type {
  ReportSchedule,
  ReportSchedulerState,
  ReportSnapshot,
} from "../../shared/report";

export interface LatestReportResponse {
  snapshot: ReportSnapshot | null;
  scheduler: ReportSchedulerState;
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    ...init,
    headers: {
      accept: "application/json",
      "content-type": "application/json",
      ...init?.headers,
    },
  });
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    throw new Error(
      (body as { error?: { message?: string } } | null)?.error?.message ??
        `Report request failed (${response.status}).`,
    );
  }
  return body as T;
}

export const getLatestReport = () => request<LatestReportResponse>("/api/reports/latest");
export const listReports = () => request<ReportSnapshot[]>("/api/reports");
export const getReport = (id: string) =>
  request<ReportSnapshot>(`/api/reports/${encodeURIComponent(id)}`);
export const generateReport = (localDate?: string) =>
  request<ReportSnapshot>("/api/reports", {
    method: "POST",
    body: JSON.stringify(localDate ? { localDate } : {}),
  });
export const retryNarrative = (id: string) =>
  request<ReportSnapshot>(`/api/reports/${encodeURIComponent(id)}/narrative`, {
    method: "POST",
    body: "{}",
  });
export const getReportSettings = () =>
  request<ReportSchedulerState>("/api/report-settings");
export const saveReportSettings = (schedule: ReportSchedule) =>
  request<ReportSchedulerState>("/api/report-settings", {
    method: "PUT",
    body: JSON.stringify(schedule),
  });
