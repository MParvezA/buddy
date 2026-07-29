import { NeedsYou } from "../features/attention/NeedsYou";
import { PlanningSection } from "../features/planning/PlanningSection";
import { RecentlyCompletedWork } from "../features/live-work/RecentlyCompletedWork";
import { ReportPreview } from "../features/reports/ReportPreview";
import { RecentSessionBriefs } from "../features/session-briefs/RecentSessionBriefs";
import { usePlanning } from "../data/planning-context";

export function DashboardSections() {
  const planning = usePlanning();
  return (
    <div className="dashboard-stack" data-testid="dashboard-sections">
      <NeedsYou timezone={planning.view?.timezone ?? "Europe/Berlin"} />

      <PlanningSection />

      <RecentSessionBriefs />

      <RecentlyCompletedWork />

      <ReportPreview />
    </div>
  );
}
