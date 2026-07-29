// @vitest-environment node
import path from "node:path";
import { fileURLToPath } from "node:url";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ObserverService } from "../../../src/server/codex/observer-service.js";
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
  });
});
