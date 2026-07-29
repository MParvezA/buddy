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
  reportPreview: {
    scheduledFor: "18:00",
    timezone: "Europe/Berlin",
    facts: [
      "1 of 4 outcomes is confirmed complete.",
      "1 outcome appears complete but still needs confirmation.",
      "1 outcome is blocked and 1 remains pending.",
      "2 active chats are unplanned work.",
      "Attention is reconciled from observed Codex state.",
    ],
    generatedInterpretation:
      "The day is moving, but the onboarding decision and dependency approval are the clearest leverage points before the evening review.",
  },
};
