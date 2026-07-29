import type {
  SessionBriefAnalysisStatus,
  SessionBriefConfidence,
  SessionBriefFailureCategory,
  SessionBriefFreshness,
  SessionBriefItem,
  SessionBriefLastGood,
  SessionBriefSnapshot,
} from "../../shared/session-briefs";
import type {
  ObserverHealthState,
  ObserverMode,
} from "../../shared/observer-types";

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

function parseLastGood(value: unknown): SessionBriefLastGood | null | undefined {
  if (value === null) return null;
  if (!value || typeof value !== "object") return undefined;
  const brief = value as Record<string, unknown>;
  if (
    typeof brief.sourceUpdatedAt !== "string" ||
    typeof brief.generatedAt !== "string" ||
    brief.generator !== "codex_app_server" ||
    brief.modelId !== "gpt-5.6-sol" ||
    typeof brief.currentState !== "string" ||
    brief.currentState.trim().length === 0 ||
    !strings(brief.done) ||
    !strings(brief.operatorActions) ||
    !strings(brief.blockers) ||
    !confidenceValues.has(brief.confidence as string) ||
    !strings(brief.evidence)
  ) {
    return undefined;
  }
  return {
    sourceUpdatedAt: brief.sourceUpdatedAt,
    generatedAt: brief.generatedAt,
    generator: "codex_app_server",
    modelId: "gpt-5.6-sol",
    currentState: brief.currentState,
    done: [...brief.done],
    operatorActions: [...brief.operatorActions],
    blockers: [...brief.blockers],
    confidence: brief.confidence as SessionBriefConfidence,
    evidence: [...brief.evidence],
  };
}

function parseItem(value: unknown): SessionBriefItem | null {
  if (!value || typeof value !== "object") return null;
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
    return null;
  }
  let failure: SessionBriefItem["failure"] = null;
  if (item.failure !== null) {
    if (!item.failure || typeof item.failure !== "object") return null;
    const candidate = item.failure as Record<string, unknown>;
    if (
      !failureCategories.has(candidate.category as string) ||
      typeof candidate.at !== "string"
    ) {
      return null;
    }
    failure = {
      category: candidate.category as SessionBriefFailureCategory,
      at: candidate.at,
    };
  }
  const lastGood = parseLastGood(item.lastGood);
  if (lastGood === undefined) return null;
  return {
    threadId: item.threadId,
    targetUpdatedAt: item.targetUpdatedAt,
    analysisStatus: item.analysisStatus as SessionBriefAnalysisStatus,
    freshness: item.freshness as SessionBriefFreshness,
    lastGood,
    failure,
    queuedAt: item.queuedAt as string | null,
    startedAt: item.startedAt as string | null,
    updatedAt: item.updatedAt,
  };
}

function finiteCount(value: unknown): value is number {
  return typeof value === "number" && Number.isSafeInteger(value) && value >= 0;
}

export function parseSessionBriefSnapshot(value: unknown): SessionBriefSnapshot {
  if (!value || typeof value !== "object") {
    throw new Error("The session-brief response could not be read.");
  }
  const snapshot = value as Record<string, unknown>;
  const rawObserver = snapshot.observer;
  const items = Array.isArray(snapshot.items)
    ? snapshot.items.map(parseItem)
    : [];
  if (
    !Array.isArray(snapshot.items) ||
    snapshot.items.length > 10 ||
    items.some((item) => item === null) ||
    !finiteCount(snapshot.total) ||
    snapshot.total !== snapshot.items.length ||
    !finiteCount(snapshot.queued) ||
    !finiteCount(snapshot.analyzing) ||
    !finiteCount(snapshot.ready) ||
    !finiteCount(snapshot.stale) ||
    !finiteCount(snapshot.unavailable) ||
    !finiteCount(snapshot.failed) ||
    typeof snapshot.selectedAt !== "string" ||
    !rawObserver ||
    typeof rawObserver !== "object" ||
    !observerStates.has((rawObserver as Record<string, unknown>).state as string) ||
    !observerCapabilities.has(
      (rawObserver as Record<string, unknown>).capability as string,
    )
  ) {
    throw new Error("The session-brief response could not be read.");
  }
  const observer = rawObserver as Record<string, unknown>;
  return {
    observer: {
      state: observer.state as ObserverHealthState,
      capability: observer.capability as ObserverMode,
    },
    selectedAt: snapshot.selectedAt,
    items: items as SessionBriefItem[],
    total: snapshot.total,
    queued: snapshot.queued,
    analyzing: snapshot.analyzing,
    ready: snapshot.ready,
    stale: snapshot.stale,
    unavailable: snapshot.unavailable,
    failed: snapshot.failed,
  };
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
