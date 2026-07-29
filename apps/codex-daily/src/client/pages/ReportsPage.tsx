import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import type { ReportSnapshot } from "../../shared/report";
import { listReports } from "../api/report-client";
import { useReports } from "../data/report-context";

export function ReportsPage() {
  const reports = useReports();
  const [history, setHistory] = useState<ReportSnapshot[]>([]);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    listReports()
      .then(setHistory)
      .catch((reason: unknown) =>
        setError(reason instanceof Error ? reason.message : "Report history could not load."),
      );
  }, [reports.latest]);
  return (
    <article className="secondary-page">
      <Link className="back-link" to="/">← Back to Today</Link>
      <header className="page-header compact">
        <div>
          <p className="eyebrow">Daily reconciliation</p>
          <h1>Report history</h1>
          <p>Immutable factual snapshots, newest first.</p>
        </div>
      </header>
      {error && <p className="inline-notice" role="alert">{error}</p>}
      {history.length ? (
        <div className="report-history">
          {history.map((snapshot) => (
            <Link className="panel report-history-card" key={snapshot.id} to={`/reports/${snapshot.id}`}>
              <span className="eyebrow">{snapshot.trigger.replace("_", " ")}</span>
              <h2>{snapshot.localDate} · snapshot {snapshot.sequence}</h2>
              <p>
                {snapshot.factualDigest.confirmedComplete.length} confirmed ·{" "}
                {snapshot.factualDigest.pending.length} pending ·{" "}
                {snapshot.factualDigest.blocked.length} blocked
              </p>
              <small>Generated {new Date(snapshot.createdAt).toLocaleString()}</small>
            </Link>
          ))}
        </div>
      ) : (
        <section className="panel empty-page">
          <span className="large-symbol" aria-hidden="true">≡</span>
          <h2>No saved reports yet</h2>
          <p>Generate a factual snapshot from Today or wait for the scheduled run.</p>
          <Link className="secondary-button link-button" to="/">Go to Today</Link>
        </section>
      )}
    </article>
  );
}
