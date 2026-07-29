import { NeedsYou } from "../features/attention/NeedsYou";
import { PlanningSection } from "../features/planning/PlanningSection";
import { LiveWorkSections } from "../features/live-work/LiveWorkSections";
import { ReportPreview } from "../features/reports/ReportPreview";
import { usePlanning } from "../data/planning-context";

export function DashboardSections() {
  const planning = usePlanning();
  return (
    <div className="dashboard-stack" data-testid="dashboard-sections">
      <NeedsYou timezone={planning.view?.timezone ?? "Europe/Berlin"} />

      <PlanningSection />

      <LiveWorkSections />

      <ReportPreview />
    </div>
  );
}
