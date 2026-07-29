import type { DashboardSnapshot } from "../shared/dashboard.js";

export const representativeDay: DashboardSnapshot = {
  mode: "representative",
  date: "2026-07-29",
  dateLabel: "Wednesday, 29 July",
  timezone: "Europe/Berlin",
  connection: {
    state: "not-connected",
    label: "Codex not connected",
    detail: "Showing representative local data for this dashboard preview.",
  },
  activeThreads: [],
  recentlyCompleted: [],
};
