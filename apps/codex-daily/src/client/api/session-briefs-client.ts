import type { SessionBriefSnapshot } from "../../shared/session-briefs";

const analysisStatuses = new Set([
  "queued",
  "analyzing",
  "ready",
  "unavailable",
  "failed",
]);
const freshnessValues = new Set(["missing", "current", "stale"]);
const confidenceValues = new Set(["high", "medium", "low"]);
const failureCategories = new Set([
  "observer_unavailable",
  "source_missing",
  "empty_usable_content",
  "analysis_unavailable",
  "timeout",
  "refusal",
  "invalid_output",
  "internal",
]);
const observerStates = new Set([
  "connecting",
  "connected",
  "reconnecting",
  "disconnected",
]);
const observerCapabilities = new Set(["standalone_history", "shared_live"]);

function strings(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === "string");
}

function nullableString(value: unknown): value is string | null {
  return value === null || typeof value === "string";
}

function isItem(value: unknown): boolean {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  if (
    typeof item.threadId !== "string" ||
    typeof item.targetUpdatedAt !== "string" ||
    !analysisStatuses.has(item.analysisStatus as string) ||
    !freshnessValues.has(item.freshness as string) ||
    !nullableString(item.queuedAt) ||
    !nullableString(item.startedAt) ||
    typeof item.updatedAt !== "string"
  ) {
    return false;
  }
  if (item.failure !== null) {
    if (!item.failure || typeof item.failure !== "object") return false;
    const failure = item.failure as Record<string, unknown>;
    if (
      !failureCategories.has(failure.category as string) ||
      typeof failure.at !== "string"
    ) {
      return false;
    }
  }
  if (item.lastGood === null) return true;
  if (!item.lastGood || typeof item.lastGood !== "object") return false;
  const brief = item.lastGood as Record<string, unknown>;
  return (
    typeof brief.sourceUpdatedAt === "string" &&
    typeof brief.generatedAt === "string" &&
    brief.generator === "codex_app_server" &&
    brief.modelId === "gpt-5.6-sol" &&
    typeof brief.currentState === "string" &&
    brief.currentState.trim().length > 0 &&
    strings(brief.done) &&
    strings(brief.operatorActions) &&
    strings(brief.blockers) &&
    confidenceValues.has(brief.confidence as string) &&
    strings(brief.evidence)
  );
}

function isSnapshot(value: unknown): value is SessionBriefSnapshot {
  if (!value || typeof value !== "object") return false;
  const snapshot = value as Partial<SessionBriefSnapshot>;
  return (
    Array.isArray(snapshot.items) &&
    snapshot.items.length <= 10 &&
    snapshot.items.every(isItem) &&
    typeof snapshot.total === "number" &&
    snapshot.total === snapshot.items.length &&
    typeof snapshot.queued === "number" &&
    typeof snapshot.analyzing === "number" &&
    typeof snapshot.ready === "number" &&
    typeof snapshot.stale === "number" &&
    typeof snapshot.unavailable === "number" &&
    typeof snapshot.failed === "number" &&
    typeof snapshot.selectedAt === "string" &&
    !!snapshot.observer &&
    observerStates.has(snapshot.observer.state) &&
    observerCapabilities.has(snapshot.observer.capability)
  );
}

export function parseSessionBriefSnapshot(value: unknown): SessionBriefSnapshot {
  if (!isSnapshot(value)) {
    throw new Error("The session-brief response could not be read.");
  }
  return value;
}

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
  let body: unknown;
  try {
    body = await response.json();
  } catch {
    throw new Error(`Session brief request failed (${response.status}).`);
  }
  if (!response.ok) {
    const errorBody = body as { error?: { message?: unknown } };
    throw new Error(
      typeof errorBody.error?.message === "string"
        ? errorBody.error.message
        : `Session brief request failed (${response.status}).`,
    );
  }
  return parseSessionBriefSnapshot(body);
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
