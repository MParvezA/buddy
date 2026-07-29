interface ConnectionIndicatorProps {
  serviceAvailable: boolean | null;
}

export function ConnectionIndicator({ serviceAvailable }: ConnectionIndicatorProps) {
  const title =
    serviceAvailable === null
      ? "Checking local service"
      : serviceAvailable
        ? "Codex not connected"
        : "Local service unavailable";
  const detail =
    serviceAvailable === false
      ? "Today’s local surface may be unavailable."
      : "Representative data · monitoring starts in a later slice";

  return (
    <div className="connection-indicator" role="status" aria-live="polite">
      <span className={`connection-dot ${serviceAvailable ? "is-demo" : ""}`} aria-hidden="true" />
      <span>
        <strong>{title}</strong>
        <small>{detail}</small>
      </span>
    </div>
  );
}
