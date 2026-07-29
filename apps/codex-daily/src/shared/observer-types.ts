export type ObserverMode = "standalone_history" | "shared_live";
export type ObserverHealthState =
  | "connecting"
  | "connected"
  | "reconnecting"
  | "disconnected";
export type ObservedThreadRuntime =
  | "unknown"
  | "not_loaded"
  | "idle"
  | "active"
  | "system_error";

export interface ObserverConnectionHealth {
  state: ObserverHealthState;
  capability: ObserverMode;
  lastSuccessfulSyncAt: string | null;
  lastInventoryRefreshAt: string | null;
  diagnostic: string | null;
}

export interface ObservedThread {
  id: string;
  sessionId: string;
  title: string | null;
  cwd: string;
  source: string;
  cliVersion: string;
  createdAt: string;
  updatedAt: string;
  recencyAt: string | null;
  archived: boolean;
  lastObservedAt: string;
  runtime: ObservedThreadRuntime;
  waitingOnApproval: boolean;
  waitingOnUserInput: boolean;
  lastActivityAt: string | null;
}

export type ObservedActivityCategory =
  | "thread"
  | "goal"
  | "turn"
  | "item"
  | "approval"
  | "input_request"
  | "error";

export interface ObservedActivity {
  sourceKey: string;
  threadId: string;
  turnId: string | null;
  itemId: string | null;
  occurredAt: string;
  category: ObservedActivityCategory;
  lifecycle: string;
  label: string;
}

export interface TaskThreadLink {
  taskId: string;
  threadId: string;
  createdAt: string;
}

export interface ObserverSnapshot {
  health: ObserverConnectionHealth;
  threads: ObservedThread[];
  activities: ObservedActivity[];
  taskLinks: TaskThreadLink[];
}

export interface ObserverSseEvent {
  id: string;
  snapshot: ObserverSnapshot;
}

/**
 * Full turn/item bodies are deliberately request-scoped and are never accepted
 * by the persistence repository or SSE DTOs.
 */
export interface TransientThreadDetail {
  thread: ObservedThread;
  activities: ObservedActivity[];
  turns: unknown[];
  fetchedAt: string;
}

export interface ObserverErrorResponse {
  error: {
    code: "validation" | "not_found" | "unavailable";
    message: string;
  };
}
