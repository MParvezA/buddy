import type {
  DeleteResult,
  OperationsDiagnostics,
} from "../../shared/operations";

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
        `Operations request failed (${response.status}).`,
    );
  }
  return body as T;
}

export const getOperationsDiagnostics = () =>
  request<OperationsDiagnostics>("/api/operations/diagnostics");

export const deleteLocalDay = (localDate: string, confirmation: string) =>
  request<DeleteResult>(`/api/operations/days/${encodeURIComponent(localDate)}`, {
    method: "DELETE",
    body: JSON.stringify({ confirmation }),
  });

export const deleteAllLocalData = (confirmation: string) =>
  request<DeleteResult>("/api/operations/data", {
    method: "DELETE",
    body: JSON.stringify({ confirmation }),
  });

