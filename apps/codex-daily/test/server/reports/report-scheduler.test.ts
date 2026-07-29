// @vitest-environment node
import { afterEach, describe, expect, it } from "vitest";
import { ReportRepository } from "../../../src/server/reports/report-repository.js";
import { ReportScheduler } from "../../../src/server/reports/report-scheduler.js";
import { ReportService } from "../../../src/server/reports/report-service.js";
import { openDatabase, type PlanningDatabase } from "../../../src/server/storage/database.js";

let database: PlanningDatabase | undefined;
afterEach(() => {
  database?.close();
  database = undefined;
});

function setup(now: { value: Date }) {
  database = openDatabase({ path: ":memory:" });
  const repository = new ReportRepository(database.connection);
  const clock = () => now.value;
  const service = new ReportService(repository, clock);
  let callback: (() => void) | null = null;
  const setTimer = ((next: () => void) => {
    callback = next;
    return { fake: true };
  }) as unknown as typeof setTimeout;
  const clearTimer = (() => {
    callback = null;
  }) as unknown as typeof clearTimeout;
  const scheduler = new ReportScheduler({
    service,
    repository,
    clock,
    setTimer,
    clearTimer,
  });
  return { repository, service, scheduler, callback: () => callback };
}

describe("report scheduler", () => {
  it("recovers only today's missed automatic slot once across restarts", async () => {
    const now = { value: new Date("2026-07-29T17:00:00.000Z") };
    const value = setup(now);
    await value.scheduler.start();
    expect(value.repository.listSnapshots().map((item) => item.trigger)).toEqual([
      "missed_recovery",
    ]);
    value.scheduler.stop();
    const restarted = new ReportScheduler({
      service: value.service,
      repository: value.repository,
      clock: () => now.value,
      setTimer: (() => ({ fake: true })) as unknown as typeof setTimeout,
      clearTimer: (() => undefined) as unknown as typeof clearTimeout,
    });
    await restarted.start();
    expect(value.repository.listSnapshots()).toHaveLength(1);
    restarted.stop();
  });

  it("runs once at the due callback and lets a manual snapshot coexist", async () => {
    const now = { value: new Date("2026-07-29T15:59:00.000Z") };
    const value = setup(now);
    await value.scheduler.start();
    expect(value.scheduler.state().nextRunAt).toBe("2026-07-29T16:00:00.000Z");
    now.value = new Date("2026-07-29T16:00:00.000Z");
    value.callback()?.();
    await new Promise((resolve) => setImmediate(resolve));
    await value.service.generate("2026-07-29", "manual");
    expect(value.repository.listSnapshots()).toHaveLength(2);
    expect(value.repository.listSnapshots().filter((item) => item.trigger === "scheduled")).toHaveLength(1);
    value.scheduler.stop();
  });

  it("uses the database uniqueness key for competing automatic claims", async () => {
    const now = { value: new Date("2026-07-29T16:00:00.000Z") };
    const value = setup(now);
    const competing = new ReportService(value.repository, () => now.value);
    const results = await Promise.all([
      value.service.generate("2026-07-29", "scheduled"),
      competing.generate("2026-07-29", "missed_recovery"),
    ]);
    expect(results.filter(Boolean)).toHaveLength(1);
    expect(value.repository.listSnapshots()).toHaveLength(1);
  });

  it("keys recovery to the configured local date across the UTC boundary", async () => {
    const now = { value: new Date("2026-07-28T22:30:00.000Z") };
    const value = setup(now);
    value.service.updateSchedule({
      time: "00:15",
      timezone: "Europe/Berlin",
      narrativeEnabled: false,
    });
    await value.scheduler.start();
    expect(value.repository.listSnapshots()).toMatchObject([
      { localDate: "2026-07-29", trigger: "missed_recovery" },
    ]);
    expect(value.repository.automaticExists("2026-07-28")).toBe(false);
    value.scheduler.stop();
  });

  it("recomputes the slot immediately after a runtime timezone preference change", async () => {
    const now = { value: new Date("2026-07-29T17:00:00.000Z") };
    const value = setup(now);
    await value.scheduler.start();
    expect(value.scheduler.operationalDiagnostics()).toMatchObject({
      lastRunTrigger: "missed_recovery",
      lastRunOutcome: "created",
      missedRunRecoveredAt: "2026-07-29T17:00:00.000Z",
    });
    value.service.updateSchedule({
      time: "18:00",
      timezone: "America/New_York",
      narrativeEnabled: false,
    });
    await value.scheduler.preferencesChanged();
    expect(value.scheduler.state().nextRunAt).toBe("2026-07-29T22:00:00.000Z");
    value.scheduler.stop();
  });

  it("does not duplicate the fall-back wall-time slot across process restarts", async () => {
    const now = { value: new Date("2026-10-25T00:31:00.000Z") };
    const value = setup(now);
    value.service.updateSchedule({
      time: "02:30",
      timezone: "Europe/Berlin",
      narrativeEnabled: false,
    });
    await value.scheduler.start();
    expect(value.repository.listSnapshots()).toHaveLength(1);
    value.scheduler.stop();

    now.value = new Date("2026-10-25T01:31:00.000Z");
    const restarted = new ReportScheduler({
      service: value.service,
      repository: value.repository,
      clock: () => now.value,
      setTimer: (() => ({ fake: true })) as unknown as typeof setTimeout,
      clearTimer: (() => undefined) as unknown as typeof clearTimeout,
    });
    await restarted.start();
    expect(value.repository.listSnapshots()).toHaveLength(1);
    restarted.stop();
  });

  it("drains an in-flight run without allowing its finally path to reschedule", async () => {
    database = openDatabase({ path: ":memory:" });
    const repository = new ReportRepository(database.connection);
    const now = { value: new Date("2026-07-29T15:59:00.000Z") };
    let resolveNarrative!: () => void;
    const narrativeWait = new Promise<void>((resolve) => {
      resolveNarrative = resolve;
    });
    const service = new ReportService(repository, () => now.value, {
      generate: async () => {
        await narrativeWait;
        return {
          reportingThreadId: "reporting-thread",
          text: "Bounded narrative",
          suggestions: [],
        };
      },
    });
    service.updateSchedule({
      time: "18:00",
      timezone: "Europe/Berlin",
      narrativeEnabled: true,
    });
    let callback: (() => void) | null = null;
    const setTimer = ((next: () => void) => {
      callback = () => {
        callback = null;
        next();
      };
      return { fake: true };
    }) as unknown as typeof setTimeout;
    const clearTimer = (() => {
      callback = null;
    }) as unknown as typeof clearTimeout;
    const scheduler = new ReportScheduler({
      service,
      repository,
      clock: () => now.value,
      setTimer,
      clearTimer,
    });
    await scheduler.start();
    now.value = new Date("2026-07-29T16:00:00.000Z");
    callback?.();
    await new Promise((resolve) => setImmediate(resolve));
    const drained = scheduler.stopAndDrain();
    expect(callback).toBeNull();
    resolveNarrative();
    await drained;
    expect(callback).toBeNull();
    expect(repository.listSnapshots()).toHaveLength(1);
  });
});
