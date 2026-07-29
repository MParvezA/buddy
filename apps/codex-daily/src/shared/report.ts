export type ReportTrigger = "manual" | "scheduled" | "missed_recovery";
export type NarrativeStatus = "not_requested" | "pending" | "ready" | "failed";

export interface ReportTaskFact {
  taskId: string;
  title: string;
  clarification: string | null;
  threadIds: string[];
}

export interface ReportUnplannedFact {
  threadId: string;
  title: string;
  activityCount: number;
  lastActivityAt: string;
}

export interface ReportAttentionFact {
  attentionId: string;
  threadId: string;
  kind: string;
  certainty: "explicit" | "possible";
  label: string;
  occurredAt: string;
}

export interface ConsiderTomorrowFact {
  kind: "task" | "unplanned_work";
  id: string;
  label: string;
  reason: "pending" | "blocked" | "unplanned";
}

export interface FactualDigest {
  localDate: string;
  cutoff: string;
  planned: ReportTaskFact[];
  confirmedComplete: ReportTaskFact[];
  suggestedComplete: ReportTaskFact[];
  pending: ReportTaskFact[];
  blocked: ReportTaskFact[];
  unplannedWork: ReportUnplannedFact[];
  outstandingAttention: ReportAttentionFact[];
  considerTomorrow: ConsiderTomorrowFact[];
}

export interface CompletionSuggestion {
  id: string;
  snapshotId: string;
  taskId: string;
  reason: string;
  sourceThreadIds: string[];
  supersededAt: string | null;
}

export interface ReportNarrative {
  status: NarrativeStatus;
  text: string | null;
  failure: string | null;
  suggestions: CompletionSuggestion[];
}

export interface ReportSnapshot {
  id: string;
  localDate: string;
  sequence: number;
  trigger: ReportTrigger;
  cutoff: string;
  factualDigest: FactualDigest;
  createdAt: string;
  narrative: ReportNarrative;
}

export interface ReportSchedule {
  time: string;
  timezone: string;
  narrativeEnabled: boolean;
}

export interface ReportSchedulerState {
  schedule: ReportSchedule;
  nextRunAt: string;
  lastAutomaticRunAt: string | null;
  lastFailure: string | null;
}

export interface UpdateReportScheduleRequest {
  time: string;
  timezone: string;
  narrativeEnabled: boolean;
}

export interface ReportErrorResponse {
  error: {
    code: "validation" | "not_found" | "conflict" | "unavailable";
    message: string;
  };
}
