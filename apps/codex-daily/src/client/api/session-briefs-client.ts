import type { SessionBriefSnapshot } from "../../shared/session-briefs";

async function request(
  url: string,
  init?: RequestInit,
): Promise<SessionBriefSnapshot> {
  const response = await fetch(url, {
    ...init,
    headers: {
      accept: "application/json",
      ...init?.headers,
    },
  });
  const body = (await response.json()) as
    | SessionBriefSnapshot
    | { error?: { message?: string } };
  if (!response.ok) {
    throw new Error(
      "error" in body && typeof body.error?.message === "string"
        ? body.error.message
        : `Session brief request failed (${response.status}).`,
    );
  }
  return body as SessionBriefSnapshot;
}

export function getSessionBriefs(): Promise<SessionBriefSnapshot> {
  return request("/api/session-briefs");
}

export function refreshSessionBriefs(): Promise<SessionBriefSnapshot> {
  return request("/api/session-briefs/refresh", { method: "POST" });
}

export function refreshSessionBrief(
  threadId: string,
): Promise<SessionBriefSnapshot> {
  return request(
    `/api/session-briefs/${encodeURIComponent(threadId)}/refresh`,
    { method: "POST" },
  );
}
