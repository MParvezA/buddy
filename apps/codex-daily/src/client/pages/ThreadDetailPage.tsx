import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import type { TransientThreadDetail } from "../../shared/observer-types";
import { getThreadDetail } from "../api/observer-client";
import { StatusBadge } from "../components/StatusBadge";
import { useObserver } from "../data/observer-context";

export function ThreadDetailPage() {
  const { threadId = "" } = useParams();
  const observer = useObserver();
  const [detail, setDetail] = useState<TransientThreadDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const thread = observer.snapshot?.threads.find((item) => item.id === threadId) ?? null;
  const activities =
    observer.snapshot?.activities.filter((item) => item.threadId === threadId) ?? [];

  useEffect(() => {
    let active = true;
    getThreadDetail(threadId)
      .then((value) => {
        if (active) setDetail(value);
      })
      .catch((reason: unknown) => {
        if (active) {
          setError(reason instanceof Error ? reason.message : "Thread detail could not be read.");
        }
      });
    return () => {
      active = false;
    };
  }, [threadId]);

  return (
    <article className="secondary-page">
      <Link className="back-link" to="/">← Back to Today</Link>
      <header className="page-header compact">
        <div>
          <p className="eyebrow">Transient Codex detail</p>
          <h1>{thread?.title ?? "Untitled Codex chat"}</h1>
          <p>
            Full history is fetched from Codex for this request only. It is not stored or sent
            through live dashboard events.
          </p>
        </div>
        {thread && (
          <StatusBadge tone={thread.runtime === "active" ? "working" : "possibly-stale"}>
            {thread.runtime.replace("_", " ")}
          </StatusBadge>
        )}
      </header>

      {!thread && !observer.loading && (
        <div className="state-panel error-state" role="alert">This observed thread was not found.</div>
      )}
      {thread && (
        <div className="detail-grid">
          <section className="panel">
            <p className="eyebrow">Current context</p>
            <h2>Observed metadata</h2>
            <dl className="metadata-list">
              <div><dt>Working directory</dt><dd>{thread.cwd}</dd></div>
              <div><dt>Source</dt><dd>{thread.source}</dd></div>
              <div><dt>CLI version</dt><dd>{thread.cliVersion}</dd></div>
              <div><dt>Retention</dt><dd>Normalized metadata only</dd></div>
              <div><dt>Codex control</dt><dd>Read-only</dd></div>
              <div>
                <dt>Transient history</dt>
                <dd>
                  {error
                    ? error
                    : detail
                      ? `${detail.turns.length} turns fetched in request memory`
                      : "Reading from Codex…"}
                </dd>
              </div>
            </dl>
          </section>
          <aside className="panel quiet-panel">
            <p className="eyebrow">Activity signals</p>
            <h2>Normalized timeline</h2>
            {activities.length === 0 ? (
              <p>No normalized activity facts are retained for this thread yet.</p>
            ) : (
              <ul className="signal-list">
                {activities.map((item) => (
                  <li key={item.sourceKey}>
                    {item.label} · <time dateTime={item.occurredAt}>{item.occurredAt}</time>
                  </li>
                ))}
              </ul>
            )}
          </aside>
        </div>
      )}
    </article>
  );
}
