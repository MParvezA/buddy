import type { ObserverHealthState, ObserverMode } from "./observer-types.js";

export type ConnectionState = "not-connected" | ObserverHealthState;
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
  activeThreads: WorkThread[];
  recentlyCompleted: CompletedWorkItem[];
}
