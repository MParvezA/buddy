import { DashboardSections } from "../components/DashboardSections";
import { useDashboardData } from "../data/dashboard-context";
import { usePlanning } from "../data/planning-context";

export function DashboardPage() {
  const { snapshot, loading, error, reload } = useDashboardData();
  const planning = usePlanning();
  const dateLabel = planning.view
    ? new Intl.DateTimeFormat("en-GB", {
        weekday: "long",
        day: "numeric",
        month: "long",
        timeZone: "UTC",
      }).format(new Date(`${planning.view.localDate}T12:00:00Z`))
    : (snapshot?.dateLabel ?? "Today");

  return (
    <>
      <header className="page-header">
        <div>
          <p className="eyebrow">Your operating day</p>
          <h1>{dateLabel}</h1>
          <p>See what needs you, what moved, and what remains—without opening every chat.</p>
        </div>
        <div className="demo-stamp">
          <span aria-hidden="true">◇</span>
          Local daily monitor
          <small>Codex metadata · read-only</small>
        </div>
      </header>

      {loading && (
        <div className="state-panel" role="status">
          <span className="loading-ring" aria-hidden="true" />
          <h2>Loading your day</h2>
          <p>Reading today’s local plan and dashboard facts.</p>
        </div>
      )}

      {!loading && error && (
        <div className="state-panel error-state" role="alert">
          <span className="state-symbol" aria-hidden="true">!</span>
          <h2>Today’s snapshot is unavailable</h2>
          <p>{error}. The shell and local navigation are still available.</p>
          <button type="button" className="secondary-button" onClick={reload}>
            Try loading again
          </button>
        </div>
      )}

      {!loading && snapshot && <DashboardSections snapshot={snapshot} />}
    </>
  );
}
