import type { DashboardSnapshot } from "../../shared/dashboard";
import { NeedsYou } from "../features/attention/NeedsYou";
import { PlanningSection } from "../features/planning/PlanningSection";
import { LiveWorkSections } from "../features/live-work/LiveWorkSections";
import { ReportPreview } from "../features/reports/ReportPreview";

interface DashboardSectionsProps {
  snapshot: DashboardSnapshot;
}

export function DashboardSections({ snapshot }: DashboardSectionsProps) {
  return (
    <div className="dashboard-stack" data-testid="dashboard-sections">
      <NeedsYou timezone={snapshot.timezone} />

      <PlanningSection />

      <LiveWorkSections />

      <ReportPreview />
    </div>
  );
}
