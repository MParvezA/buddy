import type { AttentionItem, AttentionSnapshot } from "../../shared/attention";

async function request(url: string, init?: RequestInit): Promise<AttentionSnapshot> {
  const response = await fetch(url, {
    ...init,
    headers: { accept: "application/json", ...init?.headers },
  });
  const body = (await response.json()) as
    | AttentionSnapshot
    | { error?: { message?: string } };
  if (!response.ok) {
    const message =
      "error" in body && typeof body.error?.message === "string"
        ? body.error.message
        : `Attention request failed (${response.status}).`;
    throw new Error(message);
  }
  return body as AttentionSnapshot;
}

export function getAttention(): Promise<AttentionSnapshot> {
  return request("/api/attention");
}

export function acknowledgeAttention(id: string): Promise<AttentionSnapshot> {
  return request(`/api/attention/${encodeURIComponent(id)}/acknowledge`, {
    method: "POST",
  });
}

export function dismissAttention(id: string): Promise<AttentionSnapshot> {
  return request(`/api/attention/${encodeURIComponent(id)}/dismiss`, {
    method: "POST",
  });
}

export async function getThreadAttention(threadId: string): Promise<AttentionItem[]> {
  const response = await fetch(
    `/api/attention/threads/${encodeURIComponent(threadId)}`,
    { headers: { accept: "application/json" } },
  );
  const body = (await response.json()) as
    | AttentionItem[]
    | { error?: { message?: string } };
  if (!response.ok) {
    throw new Error(
      !Array.isArray(body) && typeof body.error?.message === "string"
        ? body.error.message
        : `Attention history request failed (${response.status}).`,
    );
  }
  return body as AttentionItem[];
}
