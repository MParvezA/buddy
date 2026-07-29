// @vitest-environment node
import { afterEach, describe, expect, it, vi } from "vitest";
import { ReportRepository } from "../../../src/server/reports/report-repository.js";
import { ReportService } from "../../../src/server/reports/report-service.js";
import { openDatabase, type PlanningDatabase } from "../../../src/server/storage/database.js";

let database: PlanningDatabase | undefined;
afterEach(() => {
  database?.close();
  database = undefined;
});

function setup(
  provider?: ConstructorParameters<typeof ReportService>[2],
  repositoryFactory: (database: PlanningDatabase["connection"]) => ReportRepository =
    (connection) => new ReportRepository(connection),
) {
  database = openDatabase({ path: ":memory:" });
  const db = database.connection;
  db.prepare("INSERT INTO days(id, local_date, created_at, updated_at) VALUES ('day', ?, ?, ?)")
    .run("2026-07-29", "2026-07-29T00:00:00Z", "2026-07-29T00:00:00Z");
  db.prepare(`
    INSERT INTO tasks(
      id, day_id, title, clarification, sort_position, lifecycle,
      origin_task_id, created_at, updated_at, completed_at, closed_at
    ) VALUES ('task', 'day', 'Ship report', NULL, 0, 'open', NULL, ?, ?, NULL, NULL)
  `).run("2026-07-29T00:00:00Z", "2026-07-29T00:00:00Z");
  const repository = repositoryFactory(db);
  return {
    repository,
    service: new ReportService(
      repository,
      () => new Date("2026-07-29T16:00:00.000Z"),
      provider,
    ),
  };
}

describe("report service", () => {
  it("commits facts before narrative and stores validated interpretation separately", async () => {
    const state: { repository: ReportRepository | null } = { repository: null };
    const provider = {
      generate: vi.fn(async (input: Parameters<NonNullable<ConstructorParameters<typeof ReportService>[2]>["generate"]>[0]) => {
        expect(state.repository?.findSnapshot(input.snapshotId)?.factualDigest.planned).toHaveLength(1);
        input.registerReportingThread("reporter");
        return {
          reportingThreadId: "reporter",
          text: "A generated interpretation",
          suggestions: [{ taskId: "task", reason: "Looks complete", sourceThreadIds: [] }],
        };
      }),
    };
    const value = setup(provider);
    state.repository = value.repository;
    value.service.updateSchedule({
      time: "18:00",
      timezone: "Europe/Berlin",
      narrativeEnabled: true,
    });
    const snapshot = await value.service.generate("2026-07-29");
    expect(snapshot?.narrative).toMatchObject({
      status: "ready",
      text: "A generated interpretation",
    });
    expect(value.repository.reportingThreadId()).toBe("reporter");
    await expect(value.service.generateNarrative(snapshot!.id)).rejects.toThrow(
      /already ready/,
    );
    expect(provider.generate).toHaveBeenCalledTimes(1);
  });

  it("keeps factual history readable when narrative fails and allows narrative-only retry", async () => {
    const provider = { generate: vi.fn(async () => { throw new Error("offline"); }) };
    const { service } = setup(provider);
    service.updateSchedule({
      time: "18:00",
      timezone: "Europe/Berlin",
      narrativeEnabled: true,
    });
    const snapshot = await service.generate("2026-07-29");
    expect(snapshot?.factualDigest.planned).toHaveLength(1);
    expect(snapshot?.narrative.status).toBe("failed");
    expect(snapshot?.narrative.failure).not.toContain("offline");
    const retried = await service.generateNarrative(snapshot!.id);
    expect(retried.id).toBe(snapshot?.id);
    expect(retried.factualDigest).toEqual(snapshot?.factualDigest);
    expect(provider.generate).toHaveBeenCalledTimes(2);
  });

  it("rejects invalid schedule values without losing the stored preference", () => {
    const { service } = setup();
    expect(() =>
      service.updateSchedule({
        time: "18:00",
        timezone: "Not/AZone",
        narrativeEnabled: true,
      }),
    ).toThrow(/IANA/);
    expect(service.schedule()).toEqual({
      time: "18:00",
      timezone: "Europe/Berlin",
      narrativeEnabled: false,
    });
  });

  it("uses the retained day timezone after a mid-day preference change", async () => {
    const { repository, service } = setup();
    database!.connection
      .prepare("UPDATE days SET timezone = 'Europe/Berlin' WHERE id = 'day'")
      .run();
    database!.connection.exec(`
      INSERT INTO observed_threads(
        id, session_id, title, cwd, source, cli_version, created_at, updated_at,
        recency_at, archived, last_observed_at, runtime, waiting_on_approval,
        waiting_on_user_input, last_activity_at
      ) VALUES (
        'timezone-thread', 'timezone-session', 'Timezone work', '/workspace',
        'cli', '1', '2026-07-29T00:00:00.000Z', '2026-07-29T00:00:00.000Z',
        '2026-07-29T00:00:00.000Z', 0, '2026-07-29T00:00:00.000Z',
        'idle', 0, 0, '2026-07-29T00:00:00.000Z'
      );
      INSERT INTO observed_activities(
        source_key, thread_id, turn_id, item_id, occurred_at, category, lifecycle, label
      ) VALUES (
        'timezone-activity', 'timezone-thread', NULL, NULL,
        '2026-07-29T00:00:00.000Z', 'turn', 'completed', 'Turn completed'
      );
    `);
    service.updateSchedule({
      time: "18:00",
      timezone: "America/New_York",
      narrativeEnabled: false,
    });

    const snapshot = await service.generate("2026-07-29");

    expect(repository.findSnapshot(snapshot!.id)).toMatchObject({
      timezone: "Europe/Berlin",
      factualDigest: {
        unplannedWork: [{ threadId: "timezone-thread" }],
      },
    });
  });

  it("rejects retry while the snapshot narrative is pending", async () => {
    const { repository, service } = setup();
    const snapshot = repository.createSnapshot({
      localDate: "2026-07-29",
      dayStart: "2026-07-28T22:00:00.000Z",
      dayEnd: "2026-07-29T22:00:00.000Z",
      cutoff: "2026-07-29T16:00:00.000Z",
      trigger: "manual",
      narrativeRequested: true,
      now: "2026-07-29T16:00:00.000Z",
    });
    await expect(service.generateNarrative(snapshot.id)).rejects.toThrow(
      /already in progress/,
    );
  });

  it("keeps facts readable when narrative persistence fails", async () => {
    class FailingNarrativeRepository extends ReportRepository {
      override saveNarrative(
        ..._arguments: Parameters<ReportRepository["saveNarrative"]>
      ): void {
        void _arguments;
        throw new Error("forced narrative persistence failure");
      }
    }
    const provider = {
      generate: vi.fn(async (input: Parameters<NonNullable<ConstructorParameters<typeof ReportService>[2]>["generate"]>[0]) => ({
        reportingThreadId: "reporter",
        text: "Generated but not persisted",
        suggestions: input.digest.planned.map((task) => ({
          taskId: task.taskId,
          reason: "Looks done",
          sourceThreadIds: task.threadIds,
        })),
      })),
    };
    const { service } = setup(
      provider,
      (connection) => new FailingNarrativeRepository(connection),
    );
    service.updateSchedule({
      time: "18:00",
      timezone: "Europe/Berlin",
      narrativeEnabled: true,
    });
    const snapshot = await service.generate("2026-07-29");
    expect(snapshot?.factualDigest.planned).toHaveLength(1);
    expect(snapshot?.narrative).toMatchObject({
      status: "failed",
      text: null,
      suggestions: [],
    });
  });
});
