import type { AttentionItem } from "./attention.js";
import type { ObservedActivity, ObservedThread, TaskThreadLink } from "./observer-types.js";
import type { PlanningTask } from "./planning.js";
import type { ReportSchedule, ReportSnapshot, ReportTrigger } from "./report.js";
import type {
  SessionBriefLastGood,
  SessionBriefFailureCategory,
  SessionBriefJobReason,
} from "./session-briefs.js";

export interface RetainedCategoryCount {
  category:
    | "days"
    | "tasks"
    | "reviewDecisions"
    | "taskLinks"
    | "threads"
    | "activities"
    | "attention"
    | "reports"
    | "narratives"
    | "suggestions"
    | "observerExclusions"
    | "reportingRoles"
    | "sessionBriefs"
    | "sessionBriefJobs"
    | "preferences";
  count: number;
}

export interface RetainedDateRange {
  oldest: string | null;
  newest: string | null;
}

export interface ObserverOperationalDiagnostics {
  state: "connecting" | "connected" | "reconnecting" | "disconnected";
  lastSuccessfulSyncAt: string | null;
  reconnectAttempt: number;
  reconnectBackoffMs: number | null;
  lastErrorCategory: string | null;
  lastErrorAt: string | null;
  replayedEventCount: number;
  ignoredEventCount: number;
}

export interface SchedulerOperationalDiagnostics {
  nextRunAt: string;
  lastAutomaticRunAt: string | null;
  lastRunTrigger: ReportTrigger | null;
  lastRunOutcome: "created" | "already_exists" | "failed" | null;
  missedRunRecoveredAt: string | null;
  lastFailure: string | null;
}

export interface ReportOperationalDiagnostics {
  lastFactualReportAt: string | null;
  lastNarrativeOutcome: "ready" | "failed" | "not_requested" | "pending" | null;
}

export interface OperationsDiagnostics {
  localOnly: true;
  dataLocation: string;
  schedule: ReportSchedule;
  retainedCounts: RetainedCategoryCount[];
  retainedDates: RetainedDateRange;
  database: {
    status: "ok" | "error";
    schemaVersion: string | null;
    foreignKeyViolations: number;
  };
  observer: ObserverOperationalDiagnostics;
  scheduler: SchedulerOperationalDiagnostics;
  reports: ReportOperationalDiagnostics;
  runtime: {
    application: "codex-daily";
    version: string;
    node: string;
  };
}

export interface ExportReviewDecision {
  sourceTaskId: string;
  action: "carry_forward" | "reschedule" | "close";
  targetLocalDate: string | null;
  successorTaskId: string | null;
  decidedAt: string;
}

export interface CodexDailyExport {
  product: "codex-daily";
  schemaVersion: 2;
  exportedAt: string;
  schedule: ReportSchedule;
  days: Array<{
    id: string;
    localDate: string;
    createdAt: string;
    updatedAt: string;
    timezone: string;
  }>;
  tasks: PlanningTask[];
  reviewDecisions: ExportReviewDecision[];
  threads: ObservedThread[];
  activities: ObservedActivity[];
  taskLinks: TaskThreadLink[];
  attention: AttentionItem[];
  reports: ReportSnapshot[];
  observerExclusions: Array<{
    threadId: string;
    reason: "reporting";
    createdAt: string;
  }>;
  reportingRoles: Array<{
    threadId: string;
    role: "daily_reporter";
    createdAt: string;
  }>;
  sessionBriefs: Array<{
    threadId: string;
    lastGood: SessionBriefLastGood;
    updatedAt: string;
    outOfWindowAt: string | null;
  }>;
  sessionBriefJobs: Array<{
    threadId: string;
    jobId: string;
    targetUpdatedAt: string;
    reason: SessionBriefJobReason;
    status: "queued" | "analyzing" | "unavailable" | "failed";
    attemptCount: number;
    queuedAt: string;
    startedAt: string | null;
    failureCategory: SessionBriefFailureCategory | null;
    failureAt: string | null;
    updatedAt: string;
  }>;
}

export interface DeleteResult {
  scope: "day" | "all";
  localDate: string | null;
  deleted: RetainedCategoryCount[];
  preferencesReset: boolean;
  codexHistoryChanged: false;
  rediscoveryNotice: string;
}

export const DELETE_ALL_CONFIRMATION = "DELETE ALL CODEX DAILY DATA";
