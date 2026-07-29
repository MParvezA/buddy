// @vitest-environment node
import { afterEach, describe, expect, it, vi } from "vitest";
import { AttentionRepository } from "../../../src/server/attention/attention-repository.js";
import { AttentionEngine } from "../../../src/server/attention/attention-engine.js";
import { PrivacyService } from "../../../src/server/privacy/privacy-service.js";
import { ReportRepository } from "../../../src/server/reports/report-repository.js";
import { ReportService } from "../../../src/server/reports/report-service.js";
import { WriteCoordinator } from "../../../src/server/runtime/write-coordinator.js";
import {
  openDatabase,
  type PlanningDatabase,
} from "../../../src/server/storage/database.js";
import { ObserverRepository } from "../../../src/server/storage/observer-repository.js";
import { PlanningRepository } from "../../../src/server/storage/planning-repository.js";
import type { ObservedThread } from "../../../src/shared/observer-types.js";
import { SessionBriefRepository } from "../../../src/server/briefs/session-brief-repository.js";

let database: PlanningDatabase | undefined;

afterEach(() => {
  database?.close();
  database = undefined;
});

function observedThread(): ObservedThread {
  return {
    id: "thread-one",
    sessionId: "session-one",
    title: "Normalized work",
    cwd: "/workspace/project",
    source: "cli",
    cliVersion: "0.1",
    createdAt: "2026-07-28T22:30:00.000Z",
    updatedAt: "2026-07-29T00:00:00.000Z",
    recencyAt: "2026-07-29T00:00:00.000Z",
    archived: false,
    lastObservedAt: "2026-07-29T00:00:00.000Z",
    runtime: "idle",
    waitingOnApproval: false,
    waitingOnUserInput: false,
    lastActivityAt: "2026-07-29T00:00:00.000Z",
  };
}

function setup() {
  database = openDatabase({ path: ":memory:" });
  const db = database.connection;
  const planning = new PlanningRepository(db);
  const observer = new ObserverRepository(db);
  const attention = new AttentionRepository(db);
  const reports = new ReportRepository(db);
  const coordinator = new WriteCoordinator();
  const pauseWriters = vi.fn(async () => undefined);
  const resumeWriters = vi.fn(async () => undefined);
  const privacy = new PrivacyService({
    database: db,
    reports,
    coordinator,
    clock: () => new Date("2026-07-30T10:00:00.000Z"),
    pauseWriters,
    resumeWriters,
  });
  const briefs = new SessionBriefRepository(db, () => "brief-job");
  return {
    db,
    planning,
    observer,
    attention,
    reports,
    privacy,
    briefs,
    pauseWriters,
    resumeWriters,
  };
}

describe("local monitor privacy operations", () => {
  it("exports every monitor category with stable DTOs and no raw sensitive payload", async () => {
    const value = setup();
    const task = value.planning.createTask({
      localDate: "2026-07-29",
      timezone: "Europe/Berlin",
      title: "Plan the local release",
      clarification: null,
      position: 0,
      now: "2026-07-29T08:00:00.000Z",
    });
    value.observer.upsertThread(observedThread());
    const briefJob = value.briefs.enqueue(
      "thread-one",
      "2026-07-29T00:00:00.000Z",
      "automatic",
      "2026-07-29T10:03:00.000Z",
    )!;
    value.briefs.markAnalyzing(
      briefJob.jobId,
      "2026-07-29T10:04:00.000Z",
    );
    value.briefs.promote(
      briefJob.jobId,
      briefJob.threadId,
      briefJob.targetUpdatedAt,
      {
        content: {
          currentState: "The chat is preparing a release.",
          done: ["The chat reports the plan is ready."],
          operatorActions: ["Review the release plan."],
          blockers: [],
          confidence: "high",
          evidence: ["user:first-intent"],
        },
        generator: "codex_app_server",
        modelId: "gpt-5.6-sol",
      },
      "2026-07-29T10:05:00.000Z",
      0,
    );
    value.observer.addActivity({
      sourceKey: "turn:thread-one:turn-one:completed",
      threadId: "thread-one",
      turnId: "turn-one",
      itemId: null,
      occurredAt: "2026-07-29T10:00:00.000Z",
      category: "turn",
      lifecycle: "completed",
      label: "Turn completed",
    });
    value.observer.link(task.id, "thread-one", "2026-07-29T10:01:00.000Z");
    value.attention.upsert(
      {
        sourceKey: "turn:thread-one:turn-one:failed",
        threadId: "thread-one",
        turnId: "turn-one",
        itemId: null,
        kind: "failed_turn",
        certainty: "explicit",
        sourceOccurredAt: "2026-07-29T10:02:00.000Z",
        sourceLabel: "Turn failed",
      },
      "2026-07-29T10:02:00.000Z",
    );
    await new ReportService(
      value.reports,
      () => new Date("2026-07-29T16:00:00.000Z"),
    ).generate("2026-07-29");
    value.reports.registerReportingThread(
      "reporting-thread",
      "2026-07-29T16:01:00.000Z",
    );

    const exported = value.privacy.export();
    expect(exported).toMatchObject({
      product: "codex-daily",
      schemaVersion: 2,
      days: [{ localDate: "2026-07-29", timezone: "Europe/Berlin" }],
      tasks: [{ id: task.id }],
      taskLinks: [{ taskId: task.id, threadId: "thread-one" }],
      observerExclusions: [{ threadId: "reporting-thread", reason: "reporting" }],
      reportingRoles: [{ threadId: "reporting-thread", role: "daily_reporter" }],
      sessionBriefs: [
        {
          threadId: "thread-one",
          lastGood: {
            generator: "codex_app_server",
            modelId: "gpt-5.6-sol",
          },
        },
      ],
      sessionBriefJobs: [],
    });
    expect(exported.activities).toHaveLength(1);
    expect(exported.attention).toHaveLength(1);
    expect(exported.reports).toHaveLength(1);
    expect(JSON.stringify(exported)).not.toMatch(
      /SECRET RESPONSE|SECRET COMMAND|rawProtocol|credentials/,
    );
    expect(
      value.privacy.retainedCounts().map((item) => item.category),
    ).toEqual([
      "days",
      "tasks",
      "reviewDecisions",
      "taskLinks",
      "threads",
      "activities",
      "attention",
      "reports",
      "narratives",
      "suggestions",
      "observerExclusions",
      "reportingRoles",
      "sessionBriefs",
      "sessionBriefJobs",
      "preferences",
    ]);
    expect(value.privacy.databaseHealth()).toMatchObject({
      status: "ok",
      schemaVersion: "007_gpt_session_briefs.sql",
      foreignKeyViolations: 0,
    });
  });

  it("deletes one day using its retained timezone and shortens successor lineage", async () => {
    const value = setup();
    const source = value.planning.createTask({
      localDate: "2026-07-29",
      timezone: "Europe/Berlin",
      title: "Source",
      clarification: null,
      position: 0,
      now: "2026-07-29T00:00:00.000Z",
    });
    const successor = value.planning.createTask({
      localDate: "2026-07-30",
      timezone: "America/New_York",
      title: "Successor",
      clarification: null,
      position: 0,
      originTaskId: source.id,
      now: "2026-07-29T00:01:00.000Z",
    });
    value.planning.recordDecision({
      sourceTaskId: source.id,
      action: "reschedule",
      targetLocalDate: "2026-07-30",
      successorTaskId: successor.id,
      now: "2026-07-29T00:01:00.000Z",
    });
    value.observer.upsertThread(observedThread());
    const dayBrief = value.briefs.enqueue(
      "thread-one",
      "2026-07-29T00:00:00.000Z",
      "automatic",
      "2026-07-29T01:00:00.000Z",
    )!;
    value.briefs.markAnalyzing(
      dayBrief.jobId,
      "2026-07-29T01:01:00.000Z",
    );
    value.briefs.promote(
      dayBrief.jobId,
      dayBrief.threadId,
      dayBrief.targetUpdatedAt,
      {
        content: {
          currentState: "The chat is preparing a release.",
          done: ["The chat reports the plan is ready."],
          operatorActions: ["Review the release plan."],
          blockers: [],
          confidence: "high",
          evidence: ["user:first-intent"],
        },
        generator: "codex_app_server",
        modelId: "gpt-5.6-sol",
      },
      "2026-07-29T01:02:00.000Z",
      0,
    );
    value.observer.addActivity({
      sourceKey: "activity-in-berlin-day",
      threadId: "thread-one",
      turnId: null,
      itemId: null,
      occurredAt: "2026-07-29T00:00:00.000Z",
      category: "turn",
      lifecycle: "completed",
      label: "Turn completed",
    });
    value.attention.upsert(
      {
        sourceKey: "attention-in-berlin-day",
        threadId: "thread-one",
        turnId: null,
        itemId: null,
        kind: "explicit_blocker",
        certainty: "explicit",
        sourceOccurredAt: "2026-07-29T00:00:00.000Z",
        sourceLabel: "Explicit blocker",
      },
      "2026-07-29T00:00:00.000Z",
    );
    await new ReportService(
      value.reports,
      () => new Date("2026-07-29T16:00:00.000Z"),
    ).generate("2026-07-29");
    value.reports.updateSchedule(
      {
        time: "18:00",
        timezone: "America/New_York",
        narrativeEnabled: false,
      },
      "2026-07-29T17:00:00.000Z",
    );

    const result = await value.privacy.deleteDay(
      "2026-07-29",
      "DELETE 2026-07-29",
    );

    expect(result).toMatchObject({
      scope: "day",
      localDate: "2026-07-29",
      codexHistoryChanged: false,
    });
    expect(value.planning.findTask(source.id)).toBeNull();
    expect(value.planning.findTask(successor.id)?.originTaskId).toBeNull();
    expect(value.observer.listActivities()).toEqual([]);
    expect(value.privacy.export().sessionBriefs).toEqual([]);
    expect(value.privacy.export().sessionBriefJobs).toEqual([]);
    expect(value.observer.findThread("thread-one")?.lastActivityAt).toBeNull();
    value.observer.updateRuntime(
      "thread-one",
      "active",
      false,
      false,
      "2026-07-30T10:00:00.000Z",
    );
    new AttentionEngine(
      value.attention,
      () => new Date("2026-07-30T10:31:00.000Z"),
    ).reconcile({
      health: {
        state: "connected",
        capability: "shared_live",
        lastSuccessfulSyncAt: "2026-07-30T10:31:00.000Z",
        lastInventoryRefreshAt: "2026-07-30T10:31:00.000Z",
        diagnostic: null,
      },
      threads: value.observer.listThreads(),
      activities: value.observer.listActivities(),
      taskLinks: value.observer.listLinks(),
    });
    expect(value.attention.listOpen()).toEqual([]);
    expect(value.reports.listSnapshots()).toEqual([]);
    expect(value.observer.findThread("thread-one")).not.toBeNull();
    expect(value.pauseWriters).toHaveBeenCalledOnce();
    expect(value.resumeWriters).toHaveBeenCalledOnce();
  });

  it("rolls back a failed deletion and always resumes writers", async () => {
    const value = setup();
    value.planning.createTask({
      localDate: "2026-07-29",
      timezone: "Europe/Berlin",
      title: "Keep me",
      clarification: null,
      position: 0,
      now: "2026-07-29T08:00:00.000Z",
    });
    value.db.exec(`
      CREATE TRIGGER fail_day_deletion
      BEFORE DELETE ON days
      BEGIN
        SELECT RAISE(ABORT, 'injected local deletion failure');
      END
    `);

    await expect(
      value.privacy.deleteDay("2026-07-29", "DELETE 2026-07-29"),
    ).rejects.toThrow(/injected local deletion failure/);
    expect(value.planning.listTasks("2026-07-29")).toHaveLength(1);
    expect(value.pauseWriters).toHaveBeenCalledOnce();
    expect(value.resumeWriters).toHaveBeenCalledOnce();
    expect(value.privacy.databaseHealth().status).toBe("ok");
  });

  it("delete-all resets preferences and has no Codex mutation boundary", async () => {
    const value = setup();
    value.planning.createTask({
      localDate: "2026-07-29",
      title: "Local plan",
      clarification: null,
      position: 0,
      now: "2026-07-29T08:00:00.000Z",
    });
    value.reports.updateSchedule(
      {
        time: "21:15",
        timezone: "America/New_York",
        narrativeEnabled: true,
      },
      "2026-07-29T08:01:00.000Z",
    );

    const result = await value.privacy.deleteAll(
      "DELETE ALL CODEX DAILY DATA",
    );

    expect(result.codexHistoryChanged).toBe(false);
    expect(value.reports.getSchedule()).toEqual({
      time: "18:00",
      timezone: "Europe/Berlin",
      narrativeEnabled: false,
    });
    expect(
      value.privacy
        .retainedCounts()
        .filter((item) => item.category !== "preferences")
        .every((item) => item.count === 0),
    ).toBe(true);
    expect(value.pauseWriters).toHaveBeenCalledOnce();
    expect(value.resumeWriters).toHaveBeenCalledOnce();
  });
});
