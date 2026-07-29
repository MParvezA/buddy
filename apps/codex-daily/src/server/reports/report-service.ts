import type {
  FactualDigest,
  ReportSchedule,
  ReportSnapshot,
  ReportTrigger,
} from "../../shared/report.js";
import { localDateFor } from "../planning/local-date.js";
import {
  AutomaticReportAlreadyExistsError,
  ReportRepository,
} from "./report-repository.js";
import {
  assertReportTime,
  assertTimezone,
  reportDayBounds,
} from "./report-time.js";

export interface NarrativeResult {
  reportingThreadId: string;
  text: string;
  suggestions: Array<{
    taskId: string;
    reason: string;
    sourceThreadIds: string[];
  }>;
}

export interface ReportNarrativeProvider {
  generate(input: {
    snapshotId: string;
    digest: FactualDigest;
    existingReportingThreadId: string | null;
    registerReportingThread: (threadId: string) => void;
  }): Promise<NarrativeResult>;
}

export class ReportNotFoundError extends Error {}
export class ReportConflictError extends Error {}

export class ReportService {
  constructor(
    private readonly repository: ReportRepository,
    private readonly clock: () => Date = () => new Date(),
    private readonly narrativeProvider?: ReportNarrativeProvider,
  ) {}

  schedule(): ReportSchedule {
    return this.repository.getSchedule();
  }

  updateSchedule(input: ReportSchedule): ReportSchedule {
    if (typeof input.narrativeEnabled !== "boolean") {
      throw new Error("Narrative preference must be true or false.");
    }
    const schedule = {
      time: assertReportTime(input.time),
      timezone: assertTimezone(input.timezone),
      narrativeEnabled: input.narrativeEnabled,
    };
    return this.repository.updateSchedule(schedule, this.clock().toISOString());
  }

  currentLocalDate(): string {
    const schedule = this.schedule();
    return localDateFor(this.clock, schedule.timezone);
  }

  list(): ReportSnapshot[] {
    return this.repository.listSnapshots();
  }

  find(id: string): ReportSnapshot {
    const snapshot = this.repository.findSnapshot(id);
    if (!snapshot) throw new ReportNotFoundError("The report snapshot was not found.");
    return snapshot;
  }

  latest(localDate?: string): ReportSnapshot | null {
    return this.repository.latestSnapshot(localDate);
  }

  async generate(
    localDate: string,
    trigger: ReportTrigger = "manual",
  ): Promise<ReportSnapshot | null> {
    const schedule = this.schedule();
    const now = this.clock().toISOString();
    const bounds = reportDayBounds(localDate, schedule.timezone);
    let snapshot: ReportSnapshot;
    try {
      snapshot = this.repository.createSnapshot({
        localDate,
        dayStart: bounds.start,
        dayEnd: bounds.end,
        cutoff: now,
        trigger,
        narrativeRequested: schedule.narrativeEnabled,
        now,
      });
    } catch (error) {
      if (error instanceof AutomaticReportAlreadyExistsError) return null;
      throw error;
    }
    if (schedule.narrativeEnabled) await this.performNarrative(snapshot);
    return this.find(snapshot.id);
  }

  async generateNarrative(snapshotId: string): Promise<ReportSnapshot> {
    const snapshot = this.find(snapshotId);
    if (
      snapshot.narrative.status === "pending" ||
      snapshot.narrative.status === "ready"
    ) {
      throw new ReportConflictError(
        snapshot.narrative.status === "ready"
          ? "Generated narrative is already ready for this snapshot."
          : "Generated narrative is already in progress for this snapshot.",
      );
    }
    this.repository.markNarrativePending(snapshotId, this.clock().toISOString());
    return this.performNarrative(snapshot);
  }

  private async performNarrative(snapshot: ReportSnapshot): Promise<ReportSnapshot> {
    const snapshotId = snapshot.id;
    if (!this.narrativeProvider) {
      this.repository.failNarrative(
        snapshotId,
        "Codex narrative is unavailable",
        this.clock().toISOString(),
      );
      return this.find(snapshotId);
    }
    try {
      const result = await this.narrativeProvider.generate({
        snapshotId,
        digest: snapshot.factualDigest,
        existingReportingThreadId: this.repository.reportingThreadId(),
        registerReportingThread: (threadId) =>
          this.repository.registerReportingThread(threadId, this.clock().toISOString()),
      });
      validateNarrative(snapshot.factualDigest, result);
      this.repository.registerReportingThread(
        result.reportingThreadId,
        this.clock().toISOString(),
      );
      this.repository.saveNarrative(
        snapshotId,
        result.text.trim(),
        result.suggestions,
        this.clock().toISOString(),
      );
    } catch {
      this.repository.failNarrative(
        snapshotId,
        "Codex narrative failed",
        this.clock().toISOString(),
      );
    }
    return this.find(snapshotId);
  }
}

function validateNarrative(digest: FactualDigest, result: NarrativeResult): void {
  if (
    !result.reportingThreadId ||
    !result.text.trim() ||
    result.text.length > 8_000 ||
    !Array.isArray(result.suggestions) ||
    result.suggestions.length > 50
  ) {
    throw new Error("Narrative output is invalid.");
  }
  const taskIds = new Set(digest.planned.map((task) => task.taskId));
  const threadIdsByTask = new Map(
    digest.planned.map((task) => [task.taskId, new Set(task.threadIds)]),
  );
  for (const suggestion of result.suggestions) {
    if (
      !taskIds.has(suggestion.taskId) ||
      !suggestion.reason.trim() ||
      suggestion.reason.length > 280 ||
      suggestion.sourceThreadIds.length > 20 ||
      suggestion.sourceThreadIds.some(
        (threadId) => !threadIdsByTask.get(suggestion.taskId)?.has(threadId),
      )
    ) {
      throw new Error("Narrative suggestion is invalid.");
    }
  }
}
