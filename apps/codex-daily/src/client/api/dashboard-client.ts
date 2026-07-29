import type { DashboardSnapshot, HealthResponse } from "../../shared/dashboard";

async function getJson<T>(url: string): Promise<T> {
  const response = await fetch(url, {
    headers: { accept: "application/json" },
  });
  if (!response.ok) {
    throw new Error(`Request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

export function getHealth(): Promise<HealthResponse> {
  return getJson<HealthResponse>("/api/health");
}

export function getDashboard(): Promise<DashboardSnapshot> {
  return getJson<DashboardSnapshot>("/api/day");
}
