import type { ObserverHealthState, ObserverMode } from "./observer-types.js";

export type ConnectionState = "not-connected" | ObserverHealthState;
export type AttentionKind =
  | "approval"
  | "question"
  | "failure"
  | "interruption"
  | "blocker"
  | "possibly-stale";
export type ThreadStatus = "working" | "waiting" | "possibly-stale";

export interface HealthResponse {
  service: "codex-daily";
  status: "ok";
  mode: "observer";
  connection: {
    state: ObserverHealthState;
    capability: ObserverMode;
    diagnostic: string | null;
  };
}

export interface AttentionItem {
  id: string;
  kind: AttentionKind;
  label: string;
  title: string;
  detail: string;
  occurredAt: string;
  threadId: string;
  certainty: "explicit" | "possible";
}

export interface WorkThread {
  id: string;
  title: string;
  summary: string;
  status: ThreadStatus;
  statusLabel: string;
  lastActivityAt: string;
  linkedOutcomeIds: string[];
  isUnplanned: boolean;
}

export interface CompletedWorkItem {
  id: string;
  title: string;
  fact: string;
  completedAt: string;
  threadId: string;
}

export interface ReportPreview {
  scheduledFor: string;
  timezone: string;
  facts: string[];
  generatedInterpretation: string;
}

export interface DashboardSnapshot {
  mode: "representative";
  date: string;
  dateLabel: string;
  timezone: string;
  connection: {
    state: ConnectionState;
    label: string;
    detail: string;
  };
  attention: AttentionItem[];
  activeThreads: WorkThread[];
  recentlyCompleted: CompletedWorkItem[];
  reportPreview: ReportPreview;
}
