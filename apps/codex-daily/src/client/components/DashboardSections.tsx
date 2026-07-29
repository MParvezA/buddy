import { Link } from "react-router-dom";
import type { DashboardSnapshot } from "../../shared/dashboard";
import { NeedsYou } from "../features/attention/NeedsYou";
import { PlanningSection } from "../features/planning/PlanningSection";
import { LiveWorkSections } from "../features/live-work/LiveWorkSections";
import { StatusBadge } from "./StatusBadge";

interface DashboardSectionsProps {
  snapshot: DashboardSnapshot;
}

export function DashboardSections({ snapshot }: DashboardSectionsProps) {
  return (
    <div className="dashboard-stack" data-testid="dashboard-sections">
      <NeedsYou timezone={snapshot.timezone} />

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
