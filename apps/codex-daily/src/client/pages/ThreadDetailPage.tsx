import { Link, useParams } from "react-router-dom";
import { StatusBadge } from "../components/StatusBadge";
import { useDashboardData } from "../data/dashboard-context";

export function ThreadDetailPage() {
  const { threadId = "" } = useParams();
  const { snapshot, loading, error } = useDashboardData();

  const thread = snapshot?.activeThreads.find((item) => item.id === threadId);
  const attention = snapshot?.attention.filter((item) => item.threadId === threadId) ?? [];
  const completed = snapshot?.recentlyCompleted.filter((item) => item.threadId === threadId) ?? [];
  const title =
    thread?.title ??
    (threadId
      .split("-")
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
      .join(" ") || "Thread detail");

  return (
    <article className="secondary-page">
      <Link className="back-link" to="/">← Back to Today</Link>
      <header className="page-header compact">
        <div>
          <p className="eyebrow">Representative thread detail</p>
          <h1>{title}</h1>
          <p>Only normalized activity metadata is shown. Full chat transcripts are not retained.</p>
        </div>
        {thread && <StatusBadge tone={thread.status}>{thread.statusLabel}</StatusBadge>}
      </header>

      {loading && <div className="state-panel" role="status">Loading representative metadata…</div>}
      {error && <div className="state-panel error-state" role="alert">Thread metadata is unavailable.</div>}
      {!loading && !error && (
        <div className="detail-grid">
          <section className="panel">
            <p className="eyebrow">Current context</p>
            <h2>Observed summary</h2>
            <p className="lead-copy">
              {thread?.summary ??
                attention[0]?.detail ??
                completed[0]?.fact ??
                "This representative thread has no current activity summary."}
            </p>
            <dl className="metadata-list">
              <div><dt>Source</dt><dd>Representative local fixture</dd></div>
              <div><dt>Retention</dt><dd>Metadata only</dd></div>
              <div><dt>Codex control</dt><dd>Read-only</dd></div>
            </dl>
          </section>
          <aside className="panel quiet-panel">
            <p className="eyebrow">Activity signals</p>
            <h2>What the dashboard knows</h2>
            {attention.length === 0 && completed.length === 0 ? (
              <p>No normalized attention or completion signals are shown for this preview.</p>
            ) : (
              <ul className="signal-list">
                {attention.map((item) => <li key={item.id}>{item.label}: {item.title}</li>)}
                {completed.map((item) => <li key={item.id}>Observed completion: {item.title}</li>)}
              </ul>
            )}
          </aside>
        </div>
      )}
    </article>
  );
}
