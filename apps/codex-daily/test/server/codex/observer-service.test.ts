// @vitest-environment node
import path from "node:path";
import { fileURLToPath } from "node:url";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  DEFAULT_REPORTING_TURN_TIMEOUT_MS,
  ObserverService,
} from "../../../src/server/codex/observer-service.js";
import { openDatabase, type PlanningDatabase } from "../../../src/server/storage/database.js";
import { ObserverRepository } from "../../../src/server/storage/observer-repository.js";

const fixture = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../../fixtures/fake-codex-app-server.py",
);
let database: PlanningDatabase | undefined;
let service: ObserverService | undefined;

afterEach(async () => {
  await service?.stop();
  database?.close();
  service = undefined;
  database = undefined;
});

describe("ObserverService", () => {
  it("pages inventory, excludes children, ingests live facts, and keeps detail transient", async () => {
    database = openDatabase({ path: ":memory:" });
    const repository = new ObserverRepository(database.connection);
    service = new ObserverService({
      repository,
      executable: fixture,
      inventoryIntervalMs: 60_000,
      requestTimeoutMs: 2_000,
      clock: () => new Date("2026-07-29T12:00:00.000Z"),
    });
    await service.start();

    expect(service.snapshot().health).toMatchObject({
      state: "connected",
      capability: "standalone_history",
    });
    expect(service.snapshot().threads.map((thread) => thread.id)).toEqual([
      "thread-one",
      "thread-two",
    ]);
    await vi.waitFor(() => {
      expect(
        service?.snapshot().activities.some((activity) => activity.sourceKey.includes("turn-one")),
      ).toBe(true);
    });

    const detail = await service.detail("thread-one");
    expect(JSON.stringify(detail.turns)).toContain("SECRET RESPONSE");
    const dump = JSON.stringify({
      threads: repository.listThreads(),
      activities: repository.listActivities(),
    });
    expect(dump).not.toMatch(/SECRET RESPONSE|SECRET PREVIEW|session\.jsonl/);
  });

  it("uses the proxy fixed arguments and labels shared-live capability", async () => {
    database = openDatabase({ path: ":memory:" });
    const repository = new ObserverRepository(database.connection);
    const invocations: string[][] = [];
    const { spawn } = await import("node:child_process");
    service = new ObserverService({
      repository,
      mode: "shared_live",
      executable: fixture,
      processFactory: (executable, args) => {
        invocations.push([...args]);
        return spawn(executable, [...args], {
          shell: false,
          stdio: ["pipe", "pipe", "pipe"],
        });
      },
      inventoryIntervalMs: 60_000,
      requestTimeoutMs: 2_000,
    });
    await service.start();
    expect(invocations).toEqual([["app-server", "proxy"]]);
    expect(service.snapshot().health).toMatchObject({
      state: "connected",
      capability: "shared_live",
    });
  });

  it("keeps request episode identities distinct across process instances", async () => {
    database = openDatabase({ path: ":memory:" });
    const repository = new ObserverRepository(database.connection);
    service = new ObserverService({
      repository,
      mode: "shared_live",
      executable: fixture,
      processInstanceId: "process-one",
      inventoryIntervalMs: 60_000,
      requestTimeoutMs: 2_000,
      clock: () => new Date("2026-07-29T12:00:00.000Z"),
    });
    await service.start();
    await vi.waitFor(() => {
      expect(
        repository
          .listActivities()
          .some((activity) =>
            activity.sourceKey.includes(
              "request:process-one:connection-1:thread-one:700:pending",
            ),
          ),
      ).toBe(true);
    });
    await service.stop();

    service = new ObserverService({
      repository,
      mode: "shared_live",
      executable: fixture,
      processInstanceId: "process-two",
      inventoryIntervalMs: 60_000,
      requestTimeoutMs: 2_000,
      clock: () => new Date("2026-07-29T12:00:00.000Z"),
    });
    await service.start();
    await vi.waitFor(() => {
      const pending = repository
        .listActivities()
        .filter(
          (activity) =>
            activity.threadId === "thread-one" &&
            activity.lifecycle === "pending",
        );
      expect(pending.map((activity) => activity.sourceKey)).toEqual(
        expect.arrayContaining([
          "request:process-one:connection-1:thread-one:700:pending",
          "request:process-two:connection-1:thread-one:700:pending",
        ]),
      );
    });
  });

  it("fails visibly and schedules reconnect when the fixed child is unavailable", async () => {
    database = openDatabase({ path: ":memory:" });
    service = new ObserverService({
      repository: new ObserverRepository(database.connection),
      executable: "/definitely/not/a/codex-binary",
      requestTimeoutMs: 100,
      reconnectBaseMs: 60_000,
    });
    await service.start();
    await vi.waitFor(() => {
      expect(service?.snapshot().health.state).toBe("reconnecting");
    });
    expect(service.snapshot().threads).toEqual([]);
    expect(service.operationalDiagnostics()).toMatchObject({
      reconnectAttempt: 1,
      reconnectBackoffMs: expect.any(Number),
      lastErrorCategory: "unavailable",
      lastErrorAt: expect.any(String),
    });
    await service.stop();
    expect(service.operationalDiagnostics()).toMatchObject({
      state: "disconnected",
      reconnectBackoffMs: expect.any(Number),
    });
  });

  it("caps reconnect configuration and cancels scheduled work during shutdown", async () => {
    database = openDatabase({ path: ":memory:" });
    const scheduled = new Set<ReturnType<typeof setTimeout>>();
    const setTimer = ((callback: () => void, delay: number) => {
      const timer = setTimeout(callback, delay);
      scheduled.add(timer);
      return timer;
    }) as typeof setTimeout;
    const clearTimer = ((timer: ReturnType<typeof setTimeout>) => {
      scheduled.delete(timer);
      clearTimeout(timer);
    }) as typeof clearTimeout;
    service = new ObserverService({
      repository: new ObserverRepository(database.connection),
      executable: "/definitely/not/a/codex-binary",
      requestTimeoutMs: 100,
      reconnectBaseMs: 2_000,
      reconnectMaxMs: 2_000,
      random: () => 1,
      setTimer,
      clearTimer,
    });
    await service.start();
    await vi.waitFor(() => {
      expect(service?.operationalDiagnostics().reconnectBackoffMs).toBe(2_000);
    });
    await service.stop();
    expect(scheduled.size).toBe(0);
    expect(() =>
      new ObserverService({
        repository: new ObserverRepository(database!.connection),
        reconnectBaseMs: 500,
        reconnectMaxMs: 300_001,
      }),
    ).toThrow(/capped/);
  });

  it("serializes overlapping inventory and creation and never projects the reporting thread", async () => {
    database = openDatabase({ path: ":memory:" });
    const repository = new ObserverRepository(database.connection);
    service = new ObserverService({
      repository,
      executable: fixture,
      inventoryIntervalMs: 5,
      requestTimeoutMs: 2_000,
    });
    await service.start();
    const projectedThreadIds: string[][] = [];
    service.on("snapshot", () => {
      projectedThreadIds.push(service!.snapshot().threads.map((thread) => thread.id));
    });

    const threadId = await service.ensureReportingThread(null, (id) =>
      repository.exclude(id, "2026-07-29T12:00:00.000Z"),
    );

    expect(threadId).toBe("codex-daily-reporting-thread");
    expect(repository.isExcluded(threadId)).toBe(true);
    expect(service.snapshot().threads.map((thread) => thread.id)).not.toContain(threadId);
    await new Promise((resolve) => setTimeout(resolve, 30));
    expect(projectedThreadIds.every((ids) => !ids.includes(threadId))).toBe(true);
    expect(service.snapshot().threads.map((thread) => thread.id)).not.toContain(threadId);
  });

  it("uses a separate bounded reporting completion timeout", async () => {
    expect(DEFAULT_REPORTING_TURN_TIMEOUT_MS).toBe(120_000);
    database = openDatabase({ path: ":memory:" });
    const repository = new ObserverRepository(database.connection);
    service = new ObserverService({
      repository,
      executable: fixture,
      inventoryIntervalMs: 60_000,
      requestTimeoutMs: 2_000,
      reportingTurnTimeoutMs: 20,
    });
    await service.start();
    const threadId = await service.ensureReportingThread(null, (id) =>
      repository.exclude(id, "2026-07-29T12:00:00.000Z"),
    );
    const startedAt = Date.now();
    await expect(
      service.runReportingTurn(threadId, "NO_COMPLETION"),
    ).rejects.toThrow(/reporting turn timed out/);
    expect(Date.now() - startedAt).toBeLessThan(500);
  });
});
