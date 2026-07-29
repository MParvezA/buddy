import { Route, Routes } from "react-router-dom";
import { AppShell } from "./components/AppShell";
import { AttentionProvider } from "./data/attention-context";
import { ObserverProvider } from "./data/observer-context";
import { PlanningProvider } from "./data/planning-context";
import { DashboardPage } from "./pages/DashboardPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { ReportsPage } from "./pages/ReportsPage";
import { SettingsPage } from "./pages/SettingsPage";
import { ThreadDetailPage } from "./pages/ThreadDetailPage";
import { ReportProvider } from "./data/report-context";
import { ReportDetailPage } from "./pages/ReportDetailPage";
import { SessionBriefProvider } from "./data/session-briefs-context";

export function App() {
  return (
    <ObserverProvider>
      <SessionBriefProvider>
        <AttentionProvider>
          <PlanningProvider>
            <ReportProvider>
              <Routes>
                <Route element={<AppShell />}>
                  <Route index element={<DashboardPage />} />
                  <Route path="threads/:threadId" element={<ThreadDetailPage />} />
                  <Route path="reports" element={<ReportsPage />} />
                  <Route path="reports/:snapshotId" element={<ReportDetailPage />} />
                  <Route path="settings" element={<SettingsPage />} />
                  <Route path="*" element={<NotFoundPage />} />
                </Route>
              </Routes>
            </ReportProvider>
          </PlanningProvider>
        </AttentionProvider>
      </SessionBriefProvider>
    </ObserverProvider>
  );
}
