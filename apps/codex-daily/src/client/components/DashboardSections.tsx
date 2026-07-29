import { Link } from "react-router-dom";
import type { DashboardSnapshot } from "../../shared/dashboard";
import { PlanningSection } from "../features/planning/PlanningSection";
import { StatusBadge } from "./StatusBadge";

interface DashboardSectionsProps {
  snapshot: DashboardSnapshot;
}

function formatTime(value: string, timezone: string) {
  return new Intl.DateTimeFormat("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: timezone,
  }).format(new Date(value));
}

export function DashboardSections({ snapshot }: DashboardSectionsProps) {
  return (
    <div className="dashboard-stack" data-testid="dashboard-sections">
      <section className="panel attention-panel" data-section-order="1" aria-labelledby="attention-title">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Priority 01</p>
            <h2 id="attention-title">Needs your attention</h2>
          </div>
          <span className="count-pill">{snapshot.attention.length} open</span>
        </div>
        <ul className="card-list attention-list">
          {snapshot.attention.map((item) => (
            <li key={item.id} className={`attention-card certainty-${item.certainty}`}>
              <div className="card-meta">
                <StatusBadge tone={item.kind}>{item.label}</StatusBadge>
                <time dateTime={item.occurredAt}>{formatTime(item.occurredAt, snapshot.timezone)}</time>
              </div>
              <h3>
                <Link to={`/threads/${item.threadId}`}>{item.title}</Link>
              </h3>
              <p>{item.detail}</p>
            </li>
          ))}
        </ul>
      </section>

      <PlanningSection />

      <section className="panel" data-section-order="3" aria-labelledby="active-title">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Priority 03</p>
            <h2 id="active-title">Active Codex chats</h2>
          </div>
          <span className="count-pill neutral">{snapshot.activeThreads.length} observed</span>
        </div>
        <ul className="work-grid">
          {snapshot.activeThreads.map((thread) => (
            <li key={thread.id} className="work-card">
              <div className="card-meta">
                <StatusBadge tone={thread.status}>{thread.statusLabel}</StatusBadge>
                <time dateTime={thread.lastActivityAt}>
                  {formatTime(thread.lastActivityAt, snapshot.timezone)}
                </time>
              </div>
              <h3>
                <Link to={`/threads/${thread.id}`}>{thread.title}</Link>
              </h3>
              <p>{thread.summary}</p>
              {thread.isUnplanned && <StatusBadge tone="unplanned">Unplanned work</StatusBadge>}
            </li>
          ))}
        </ul>
      </section>

      <section className="panel" data-section-order="4" aria-labelledby="completed-title">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Priority 04</p>
            <h2 id="completed-title">Recently completed work</h2>
          </div>
          <span className="section-hint">Observed facts, not task confirmation</span>
        </div>
        <ul className="completed-list">
          {snapshot.recentlyCompleted.map((item) => (
            <li key={item.id}>
              <span className="completion-mark" aria-hidden="true">✓</span>
              <div>
                <h3>
                  <Link to={`/threads/${item.threadId}`}>{item.title}</Link>
                </h3>
                <p>{item.fact}</p>
              </div>
              <time dateTime={item.completedAt}>{formatTime(item.completedAt, snapshot.timezone)}</time>
            </li>
          ))}
        </ul>
      </section>

      <section className="panel report-panel" data-section-order="5" aria-labelledby="report-title">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Priority 05</p>
            <h2 id="report-title">Evening-report preview</h2>
          </div>
          <Link className="text-link" to="/reports">
            Open report history <span aria-hidden="true">→</span>
          </Link>
        </div>
        <div className="report-grid">
          <div className="fact-block">
            <div className="block-label">
              <StatusBadge tone="fact">Recorded facts</StatusBadge>
              <span>
                Scheduled {snapshot.reportPreview.scheduledFor} · {snapshot.reportPreview.timezone}
              </span>
            </div>
            <ul>
              {snapshot.reportPreview.facts.map((fact) => (
                <li key={fact}>{fact}</li>
              ))}
            </ul>
          </div>
          <aside className="interpretation-block" aria-label="Generated interpretation preview">
            <StatusBadge tone="generated">Generated interpretation</StatusBadge>
            <p>{snapshot.reportPreview.generatedInterpretation}</p>
            <small>Interpretation is secondary to the recorded facts.</small>
          </aside>
        </div>
      </section>
    </div>
  );
}
