import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import type { AttentionItem } from "../../shared/attention";
import type { ThreadDetail } from "../../shared/observer-types";
import { getThreadAttention } from "../api/attention-client";
import { getThreadDetail } from "../api/observer-client";
import { StatusBadge } from "../components/StatusBadge";
import { useObserver } from "../data/observer-context";

export function ThreadDetailPage() {
  const { threadId = "" } = useParams();
  const observer = useObserver();
  const [detail, setDetail] = useState<ThreadDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [attentionHistory, setAttentionHistory] = useState<AttentionItem[]>([]);
  const [attentionLoading, setAttentionLoading] = useState(true);
  const [attentionError, setAttentionError] = useState<string | null>(null);
  const thread = observer.snapshot?.threads.find((item) => item.id === threadId) ?? null;
  const activities = detail?.activities ?? [];

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

  useEffect(() => {
    let active = true;
    getThreadAttention(threadId)
      .then((value) => {
        if (active) {
          setAttentionHistory(value);
          setAttentionError(null);
        }
      })
      .catch((reason: unknown) => {
        if (active) {
          setAttentionError(
            reason instanceof Error
              ? reason.message
              : "Attention history could not be loaded.",
          );
        }
      })
      .finally(() => {
        if (active) setAttentionLoading(false);
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
            Full history is fetched from Codex for this request only when connected
            and is never stored or sent through live dashboard events. Retained
            normalized facts stay available locally.
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
                  {error ? (
                    error
                  ) : !detail ? (
                    "Checking Codex availability…"
                  ) : detail.transientHistory.status === "available" ? (
                    `${detail.transientHistory.turns.length} turns fetched in request memory`
                  ) : (
                    detail.transientHistory.reason
                  )}
                </dd>
              </div>
            </dl>
          </section>
          <aside className="panel quiet-panel">
            <p className="eyebrow">Activity signals</p>
            <h2>Normalized timeline</h2>
            {!detail && !error ? (
              <p role="status">Loading normalized activity…</p>
            ) : activities.length === 0 ? (
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
            <h3 className="detail-subheading">Attention projection history</h3>
            {attentionLoading ? (
              <p role="status">Loading attention history…</p>
            ) : attentionError ? (
              <p className="inline-notice" role="alert">{attentionError}</p>
            ) : attentionHistory.length === 0 ? (
              <p>No attention projections are retained for this thread.</p>
            ) : (
              <ul className="signal-list">
                {attentionHistory.map((item) => (
                  <li key={item.id}>
                    {item.sourceLabel} · {item.lifecycle.replace("_", " ")}
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
