import type { ObserverHealthState, ObserverMode } from "./observer-types.js";

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
