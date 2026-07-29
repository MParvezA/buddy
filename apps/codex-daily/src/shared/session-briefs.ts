import type {
  ObserverHealthState,
  ObserverMode,
} from "./observer-types.js";

export type SessionBriefAnalysisStatus =
  | "queued"
  | "analyzing"
  | "ready"
  | "unavailable"
  | "failed";
export type SessionBriefFreshness = "missing" | "current" | "stale";
export type SessionBriefConfidence = "high" | "medium" | "low";
export type SessionBriefFailureCategory =
  | "observer_unavailable"
  | "source_missing"
  | "empty_usable_content"
  | "analysis_unavailable"
  | "timeout"
  | "refusal"
  | "invalid_output"
  | "internal";
export type SessionBriefJobReason = "automatic" | "manual" | "retry";

export interface SessionBriefContent {
  currentState: string;
  done: string[];
  operatorActions: string[];
  blockers: string[];
  confidence: SessionBriefConfidence;
  evidence: string[];
}

export interface SessionBriefLastGood extends SessionBriefContent {
  sourceUpdatedAt: string;
  generatedAt: string;
  generator: string;
  modelId: string | null;
}

export interface SessionBriefFailure {
  category: SessionBriefFailureCategory;
  at: string;
}

export interface SessionBriefItem {
  threadId: string;
  targetUpdatedAt: string;
  analysisStatus: SessionBriefAnalysisStatus;
  freshness: SessionBriefFreshness;
  lastGood: SessionBriefLastGood | null;
  failure: SessionBriefFailure | null;
  queuedAt: string | null;
  startedAt: string | null;
  updatedAt: string;
}

export interface SessionBriefSnapshot {
  observer: {
    state: ObserverHealthState;
    capability: ObserverMode;
  };
  selectedAt: string;
  items: SessionBriefItem[];
  total: number;
  queued: number;
  analyzing: number;
  ready: number;
  stale: number;
  unavailable: number;
  failed: number;
}

export interface SessionBriefSseEvent {
  id: string;
  snapshot: SessionBriefSnapshot;
}

export interface SessionBriefErrorResponse {
  error: {
    code:
      | "validation"
      | "not_found"
      | "not_selected"
      | "observer_unavailable";
    message: string;
  };
}
