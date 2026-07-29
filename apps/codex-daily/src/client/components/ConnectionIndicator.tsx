import type { ObserverConnectionHealth } from "../../shared/observer-types";

interface ConnectionIndicatorProps {
  health: ObserverConnectionHealth | null;
}

export function ConnectionIndicator({ health }: ConnectionIndicatorProps) {
  const title = health ? `Codex ${health.state}` : "Checking Codex observer";
  const detail = health
    ? health.capability === "standalone_history"
      ? "History polling · live coverage is limited"
      : "Shared live observer"
    : "Local planning remains available";
  return (
    <div className="connection-indicator" role="status" aria-live="polite">
      <span className={`connection-dot ${health?.state === "connected" ? "is-live" : ""}`} aria-hidden="true" />
      <span>
        <strong>{title}</strong>
        <small>{health?.diagnostic ?? detail}</small>
      </span>
    </div>
  );
}
