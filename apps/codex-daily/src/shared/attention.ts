import type {
  ObserverHealthState,
  ObserverMode,
} from "./observer-types.js";

export type AttentionKind =
  | "approval"
  | "direct_question"
  | "failed_turn"
  | "interrupted_turn"
  | "explicit_blocker"
  | "possibly_stale";

export type AttentionCertainty = "explicit" | "possible";
export type AttentionLifecycle =
  | "open"
  | "acknowledged"
  | "dismissed"
  | "source_resolved";

export interface AttentionItem {
  id: string;
  sourceKey: string;
  threadId: string;
  turnId: string | null;
  itemId: string | null;
  kind: AttentionKind;
  certainty: AttentionCertainty;
  sourceOccurredAt: string;
  lastDerivedAt: string;
  sourceLabel: string;
  lifecycle: AttentionLifecycle;
  localActionAt: string | null;
}

export interface AttentionSnapshot {
  capability: ObserverMode;
  connectionState: ObserverHealthState;
  liveRequestCoverage: "available" | "external_clients_unavailable";
  items: AttentionItem[];
}

export interface AttentionErrorResponse {
  error: {
    code: "validation" | "not_found" | "not_actionable";
    message: string;
  };
}
