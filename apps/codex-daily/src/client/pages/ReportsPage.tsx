import { Link } from "react-router-dom";
import { StatusBadge } from "../components/StatusBadge";
import { useDashboardData } from "../data/dashboard-context";

export function ReportsPage() {
  const { snapshot } = useDashboardData();
  return (
    <article className="secondary-page">
      <Link className="back-link" to="/">← Back to Today</Link>
      <header className="page-header compact">
        <div>
          <p className="eyebrow">Daily reconciliation</p>
          <h1>Report history</h1>
          <p>Reports will become durable snapshots in a later slice.</p>
        </div>
      </header>
      <section className="panel empty-page">
        <span className="large-symbol" aria-hidden="true">≡</span>
        <StatusBadge tone="fact">Representative preview only</StatusBadge>
        <h2>No saved reports yet</h2>
        <p>
          Today’s factual preview is scheduled for {snapshot?.reportPreview.scheduledFor ?? "18:00"}{" "}
          {snapshot?.reportPreview.timezone ?? "Europe/Berlin"}. This view remains read-only.
        </p>
        <Link className="secondary-button link-button" to="/">View today’s preview</Link>
      </section>
    </article>
  );
}
