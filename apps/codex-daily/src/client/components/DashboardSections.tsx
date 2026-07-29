import { Link } from "react-router-dom";
import type { DashboardSnapshot } from "../../shared/dashboard";
import { PlanningSection } from "../features/planning/PlanningSection";
import { LiveWorkSections } from "../features/live-work/LiveWorkSections";
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

      <LiveWorkSections />

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
