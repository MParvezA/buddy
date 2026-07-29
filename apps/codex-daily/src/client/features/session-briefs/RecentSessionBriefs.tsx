import { useObserver } from "../../data/observer-context";
import { usePlanning } from "../../data/planning-context";
import { useSessionBriefs } from "../../data/session-briefs-context";
import { SessionBriefCard } from "./SessionBriefCard";

function progressCopy(snapshot: NonNullable<ReturnType<typeof useSessionBriefs>["snapshot"]>) {
  const parts = [
    [snapshot.analyzing, "analyzing"],
    [snapshot.queued, "queued"],
    [snapshot.ready, "ready"],
    [snapshot.failed, "failed"],
    [snapshot.unavailable, "unavailable"],
    [snapshot.stale, "stale"],
  ] as const;
  const visible = parts
    .filter(([count]) => count > 0)
    .map(([count, label]) => `${count} ${label}`);
  return visible.length > 0 ? visible.join(" · ") : "No brief work in progress";
}

export function RecentSessionBriefs() {
  const observer = useObserver();
  const planning = usePlanning();
  const briefs = useSessionBriefs();
  const timezone = planning.view?.timezone ?? "Europe/Berlin";
  const snapshot = briefs.snapshot;
  const canAnalyze = snapshot?.observer.state === "connected";
  const threads = new Map(
    (observer.snapshot?.threads ?? []).map((thread) => [thread.id, thread]),
  );

  return (
    <section
      className="panel session-briefs-panel"
      data-section-order="3"
      aria-labelledby="session-briefs-title"
    >
      <div className="section-heading session-briefs-heading">
        <div>
          <p className="eyebrow">Priority 03</p>
          <h2 id="session-briefs-title">Recent session briefs</h2>
        </div>
        <div className="session-brief-actions">
          <span className="count-pill neutral">
            {snapshot
              ? snapshot.total >= 10
                ? "10 recent"
                : `${snapshot.total} available`
              : "Loading"}
          </span>
          <button
            type="button"
            className="primary-button"
            disabled={!snapshot || !canAnalyze}
            aria-disabled={!snapshot || !canAnalyze || briefs.refreshingAll}
            onClick={() => {
              if (!briefs.refreshingAll) void briefs.refreshAll();
            }}
          >
            {briefs.refreshingAll ? "Refreshing 10 briefs…" : "Refresh 10 briefs"}
          </button>
        </div>
      </div>

      <p className="brief-progress" role="status" aria-live="polite" aria-atomic="true">
        {snapshot ? progressCopy(snapshot) : "Loading recent session briefs…"}
      </p>

      {briefs.loadError && (
        <p className="inline-notice" role="alert">
          {briefs.loadError} Factual planning and monitoring remain available.
        </p>
      )}
      {briefs.streamError && (
        <p className="inline-notice">{briefs.streamError}</p>
      )}
      {briefs.mutationError && (
        <p className="inline-notice error-message" role="alert">
          {briefs.mutationError}
        </p>
      )}
      {snapshot && !canAnalyze && (
        <p className="inline-notice">
          Brief refresh is unavailable while Codex is {snapshot.observer.state}.
          Last-known briefs and factual session metadata remain visible.
        </p>
      )}
      {briefs.loading && !snapshot && !briefs.loadError && (
        <p className="quiet-copy">Loading recent session briefs…</p>
      )}
      {snapshot && snapshot.items.length === 0 && (
        <div className="empty-inline">
          <h3>No eligible Codex sessions</h3>
          <p>
            Planning stays available. Briefs will appear after an ordinary Codex
            session is observed.
          </p>
        </div>
      )}
      {snapshot && snapshot.items.length > 0 && (
        <ul className="session-brief-grid">
          {snapshot.items.map((item) => {
            const thread = threads.get(item.threadId) ?? null;
            return (
              <SessionBriefCard
                key={item.threadId}
                item={item}
                thread={thread}
                timezone={timezone}
                canAnalyze={canAnalyze}
                retryPending={briefs.pendingThreadIds.has(item.threadId)}
                linked={
                  observer.snapshot?.taskLinks.some(
                    (link) => link.threadId === item.threadId,
                  ) ?? false
                }
                onRetry={(threadId) => void briefs.refreshThread(threadId)}
              />
            );
          })}
        </ul>
      )}
      {snapshot && snapshot.total > 0 && snapshot.total < 10 && (
        <p className="section-hint session-brief-count-note">
          Showing all {snapshot.total} eligible sessions currently available.
        </p>
      )}
    </section>
  );
}
