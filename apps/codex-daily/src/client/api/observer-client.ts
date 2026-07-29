import type {
  ObserverSnapshot,
  TransientThreadDetail,
} from "../../shared/observer-types";

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    ...init,
    headers: { accept: "application/json", ...init?.headers },
  });
  const body = (await response.json()) as T | { error?: { message?: string } };
  if (!response.ok) {
    const message =
      "error" in (body as object) &&
      typeof (body as { error?: { message?: string } }).error?.message === "string"
        ? (body as { error: { message: string } }).error.message
        : `Observer request failed (${response.status}).`;
    throw new Error(message);
  }
  return body as T;
}

export function getObserver(): Promise<ObserverSnapshot> {
  return request("/api/observer");
}

export function getThreadDetail(threadId: string): Promise<TransientThreadDetail> {
  return request(`/api/observer/threads/${encodeURIComponent(threadId)}`, {
    cache: "no-store",
  });
}

export function linkTask(taskId: string, threadId: string): Promise<ObserverSnapshot> {
  return request(
    `/api/tasks/${encodeURIComponent(taskId)}/threads/${encodeURIComponent(threadId)}`,
    { method: "PUT" },
  );
}

export function unlinkTask(taskId: string, threadId: string): Promise<ObserverSnapshot> {
  return request(
    `/api/tasks/${encodeURIComponent(taskId)}/threads/${encodeURIComponent(threadId)}`,
    { method: "DELETE" },
  );
}
