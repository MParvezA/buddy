import { useState } from "react";
import { Link } from "react-router-dom";
import type { ObservedThread } from "../../../shared/observer-types";
import { useObserver } from "../../data/observer-context";
import { usePlanning } from "../../data/planning-context";
import { StatusBadge } from "../../components/StatusBadge";

function formatTime(value: string | null, timezone: string) {
  if (!value) return "No activity yet";
  return new Intl.DateTimeFormat("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: timezone,
  }).format(new Date(value));
}

function threadTone(thread: ObservedThread): "working" | "waiting" | "possibly-stale" {
  if (thread.waitingOnApproval || thread.waitingOnUserInput) return "waiting";
  if (thread.runtime === "active") return "working";
  return "possibly-stale";
}

function threadStatus(thread: ObservedThread): string {
  if (thread.waitingOnApproval) return "Waiting on approval";
  if (thread.waitingOnUserInput) return "Waiting on your input";
  if (thread.runtime === "active") return "Working";
  if (thread.runtime === "idle") return "Idle";
  if (thread.runtime === "not_loaded") return "History only";
  if (thread.runtime === "system_error") return "System error";
  return "Unknown";
}

function ThreadLinks({ thread }: { thread: ObservedThread }) {
  const planning = usePlanning();
  const observer = useObserver();
  const [selected, setSelected] = useState("");
  const links = observer.snapshot?.taskLinks.filter((link) => link.threadId === thread.id) ?? [];
  const available =
    planning.view?.tasks.filter((task) => !links.some((link) => link.taskId === task.id)) ?? [];

  return (
    <div className="thread-links">
      {links.map((link) => {
        const task = planning.view?.tasks.find((item) => item.id === link.taskId);
        return (
          <span className="thread-link-chip" key={link.taskId}>
            {task?.title ?? "Linked outcome"}
            <button
              type="button"
              aria-label={`Unlink ${task?.title ?? "outcome"} from ${thread.title ?? "Codex chat"}`}
              disabled={observer.pendingLink === `${link.taskId}:${thread.id}`}
              onClick={() => void observer.unlinkTask(link.taskId, thread.id)}
            >
              ×
            </button>
          </span>
        );
      })}
      {available.length > 0 && (
        <form
          className="thread-link-form"
          onSubmit={(event) => {
            event.preventDefault();
            if (!selected) return;
            void observer.linkTask(selected, thread.id).then(() => setSelected(""));
          }}
        >
          <label>
            <span className="visually-hidden">Link an outcome to {thread.title ?? "Codex chat"}</span>
            <select value={selected} onChange={(event) => setSelected(event.target.value)}>
              <option value="">Link outcome…</option>
              {available.map((task) => (
                <option key={task.id} value={task.id}>{task.title}</option>
              ))}
            </select>
          </label>
          <button type="submit" className="text-button" disabled={!selected}>Link</button>
        </form>
      )}
      {links.length === 0 && available.length === 0 && (
        <small>No outcomes available to link.</small>
      )}
    </div>
  );
}

export function LiveWorkSections() {
  const observer = useObserver();
  const planning = usePlanning();
  const timezone = planning.view?.timezone ?? "Europe/Berlin";
  const observedThreads =
    observer.snapshot?.threads.filter((thread) => !thread.archived) ?? [];
  const threads = [...observedThreads]
    .sort(
      (left, right) =>
        Number(right.runtime === "active") - Number(left.runtime === "active") ||
        (right.recencyAt ?? right.updatedAt).localeCompare(
          left.recencyAt ?? left.updatedAt,
        ),
    )
    .slice(0, 20);
  const recent = (observer.snapshot?.activities ?? [])
    .filter((item) => item.category === "turn" && item.lifecycle === "completed")
    .slice(0, 8);

  return (
    <>
      <section className="panel" data-section-order="3" aria-labelledby="active-title">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Priority 03</p>
            <h2 id="active-title">Active and recent Codex chats</h2>
          </div>
          <span className="count-pill neutral">{observedThreads.length} observed</span>
        </div>
        {observer.error && <p className="inline-notice" role="status">{observer.error}</p>}
        {observer.loading && <p className="quiet-copy">Loading observed Codex metadata…</p>}
        {!observer.loading && threads.length === 0 && (
          <div className="empty-inline">
            <h3>No Codex chats observed yet</h3>
            <p>
              Planning stays available. The monitor will refresh history when the local Codex
              connection is available.
            </p>
          </div>
        )}
        <ul className="work-grid">
          {threads.map((thread) => {
            const linked = observer.snapshot?.taskLinks.some(
              (link) => link.threadId === thread.id,
            );
            return (
              <li key={thread.id} className="work-card">
                <div className="card-meta">
                  <StatusBadge tone={threadTone(thread)}>{threadStatus(thread)}</StatusBadge>
                  <time dateTime={thread.lastActivityAt ?? thread.updatedAt}>
                    {formatTime(thread.lastActivityAt ?? thread.updatedAt, timezone)}
                  </time>
                </div>
                <h3><Link to={`/threads/${thread.id}`}>{thread.title ?? "Untitled Codex chat"}</Link></h3>
                <p className="thread-metadata">{thread.cwd} · {thread.source}</p>
                {!linked && <StatusBadge tone="unplanned">Unplanned work</StatusBadge>}
                <ThreadLinks thread={thread} />
              </li>
            );
          })}
        </ul>
        {observedThreads.length > threads.length && (
          <p className="section-hint">
            Showing the 20 most relevant chats, with active chats first.
          </p>
        )}
      </section>

      <section className="panel" data-section-order="4" aria-labelledby="completed-title">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Priority 04</p>
            <h2 id="completed-title">Recently completed work</h2>
          </div>
          <span className="section-hint">Observed turn facts, not task confirmation</span>
        </div>
        {recent.length === 0 ? (
          <div className="empty-inline">
            <p>No completed Codex turns have been observed.</p>
          </div>
        ) : (
          <ul className="completed-list">
            {recent.map((item) => {
              const thread = observer.snapshot?.threads.find(
                (candidate) => candidate.id === item.threadId,
              );
              return (
                <li key={item.sourceKey}>
                  <span className="completion-mark" aria-hidden="true">✓</span>
                  <div>
                    <h3>
                      <Link to={`/threads/${item.threadId}`}>
                        {thread?.title ?? "Untitled Codex chat"}
                      </Link>
                    </h3>
                    <p>{item.label}</p>
                  </div>
                  <time dateTime={item.occurredAt}>{formatTime(item.occurredAt, timezone)}</time>
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </>
  );
}
