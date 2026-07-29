import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import type { ReportSnapshot } from "../../shared/report";
import { listReports } from "../api/report-client";
import { useReports } from "../data/report-context";

export function ReportsPage() {
  const reports = useReports();
  const [history, setHistory] = useState<ReportSnapshot[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let active = true;
    listReports()
      .then((value) => {
        if (active) {
          setHistory(value);
          setError(null);
        }
      })
      .catch((reason: unknown) => {
        if (active) {
          setError(reason instanceof Error ? reason.message : "Report history could not load.");
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
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
      {loading && <p className="state-panel" role="status">Loading report history…</p>}
      {!loading && !error && history.length ? (
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
      ) : !loading && !error ? (
        <section className="panel empty-page">
          <span className="large-symbol" aria-hidden="true">≡</span>
          <h2>No saved reports yet</h2>
          <p>Generate a factual snapshot from Today or wait for the scheduled run.</p>
          <Link className="secondary-button link-button" to="/">Go to Today</Link>
        </section>
      ) : null}
    </article>
  );
}
