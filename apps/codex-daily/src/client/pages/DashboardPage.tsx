import { DashboardSections } from "../components/DashboardSections";
import { useDashboardData } from "../data/dashboard-context";

export function DashboardPage() {
  const { snapshot, loading, error, reload } = useDashboardData();

  return (
    <>
      <header className="page-header">
        <div>
          <p className="eyebrow">Your operating day</p>
          <h1>{snapshot?.dateLabel ?? "Today"}</h1>
          <p>See what needs you, what moved, and what remains—without opening every chat.</p>
        </div>
        <div className="demo-stamp">
          <span aria-hidden="true">◇</span>
          Representative day
          <small>Read-only preview</small>
        </div>
      </header>

      {loading && (
        <div className="state-panel" role="status">
          <span className="loading-ring" aria-hidden="true" />
          <h2>Loading your day</h2>
          <p>Reading the representative snapshot from the local service.</p>
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
