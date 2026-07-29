// @vitest-environment node
import Fastify, { type FastifyInstance } from "fastify";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { afterEach, describe, expect, it } from "vitest";
import { registerObserverRoutes } from "../../../src/server/codex/observer-routes.js";
import { ObserverService } from "../../../src/server/codex/observer-service.js";
import { openDatabase, type PlanningDatabase } from "../../../src/server/storage/database.js";
import { ObserverRepository } from "../../../src/server/storage/observer-repository.js";
import { PlanningRepository } from "../../../src/server/storage/planning-repository.js";
import type { ObservedThread } from "../../../src/shared/observer-types.js";

const fixture = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../../fixtures/fake-codex-app-server.py",
);
let app: FastifyInstance | undefined;
let service: ObserverService | undefined;
let database: PlanningDatabase | undefined;

afterEach(async () => {
  await app?.close();
  await service?.stop();
  database?.close();
  app = undefined;
  service = undefined;
  database = undefined;
});

describe("observer routes", () => {
  it("serves safe snapshots, transient detail, and idempotent local links", async () => {
    database = openDatabase({ path: ":memory:" });
    const observerRepository = new ObserverRepository(database.connection);
    const task = new PlanningRepository(database.connection).createTask({
      localDate: "2026-07-29",
      title: "Link this outcome",
      clarification: null,
      position: 0,
      now: "2026-07-29T12:00:00.000Z",
    });
    service = new ObserverService({
      repository: observerRepository,
      executable: fixture,
      inventoryIntervalMs: 60_000,
      requestTimeoutMs: 2_000,
    });
    await service.start();
    app = Fastify({ logger: false });
    await registerObserverRoutes(app, service, 50);

    const snapshot = await app.inject({ method: "GET", url: "/api/observer" });
    expect(snapshot.statusCode).toBe(200);
    expect(snapshot.body).not.toMatch(/SECRET|preview|turns|command|diff/);

    const detail = await app.inject({
      method: "GET",
      url: "/api/observer/threads/thread-one",
    });
    expect(detail.statusCode).toBe(200);
    expect(detail.headers["cache-control"]).toBe("no-store");
    expect(detail.body).toContain("SECRET RESPONSE");
    expect(detail.json().activities.length).toBeGreaterThan(0);
    expect(detail.json().transientHistory).toMatchObject({
      status: "available",
      turns: expect.any(Array),
    });
    expect((await app.inject({ method: "GET", url: "/api/observer" })).body).not.toContain(
      "SECRET RESPONSE",
    );

    for (let attempt = 0; attempt < 2; attempt += 1) {
      const linked = await app.inject({
        method: "PUT",
        url: `/api/tasks/${task.id}/threads/thread-one`,
      });
      expect(linked.statusCode).toBe(200);
      expect(linked.json().taskLinks).toHaveLength(1);
    }
    const removed = await app.inject({
      method: "DELETE",
      url: `/api/tasks/${task.id}/threads/thread-one`,
    });
    expect(removed.statusCode).toBe(200);
    expect(removed.json().taskLinks).toEqual([]);
  });

  it("serves retained metadata and activity when transient history is unavailable", async () => {
    database = openDatabase({ path: ":memory:" });
    const repository = new ObserverRepository(database.connection);
    const now = "2026-07-29T12:00:00.000Z";
    const thread: ObservedThread = {
      id: "retained-thread",
      sessionId: "retained-session",
      title: "Retained offline work",
      cwd: "/workspace/retained",
      source: "cli",
      cliVersion: "0.146.0",
      createdAt: now,
      updatedAt: now,
      recencyAt: now,
      archived: false,
      lastObservedAt: now,
      runtime: "unknown",
      waitingOnApproval: false,
      waitingOnUserInput: false,
      lastActivityAt: now,
    };
    repository.upsertThread(thread);
    repository.addActivity({
      sourceKey: "turn:retained-thread:turn-one:failed",
      threadId: thread.id,
      turnId: "turn-one",
      itemId: null,
      occurredAt: now,
      category: "turn",
      lifecycle: "failed",
      label: "Turn failed",
    });
    service = new ObserverService({ repository });
    app = Fastify({ logger: false });
    await registerObserverRoutes(app, service);

    const detail = await app.inject({
      method: "GET",
      url: "/api/observer/threads/retained-thread",
    });

    expect(detail.statusCode).toBe(200);
    expect(detail.headers["cache-control"]).toBe("no-store");
    expect(detail.json()).toMatchObject({
      thread: { id: "retained-thread", title: "Retained offline work" },
      activities: [{ sourceKey: "turn:retained-thread:turn-one:failed" }],
      transientHistory: {
        status: "unavailable",
        reason: "Codex is disconnected; full history is unavailable.",
      },
    });
    expect(detail.body).not.toContain("turns");
  });

  it("validates IDs and filters reporting exclusions at route boundaries", async () => {
    database = openDatabase({ path: ":memory:" });
    const repository = new ObserverRepository(database.connection);
    repository.exclude("thread-one", "2026-07-29T12:00:00.000Z");
    service = new ObserverService({
      repository,
      executable: fixture,
      inventoryIntervalMs: 60_000,
      requestTimeoutMs: 2_000,
    });
    await service.start();
    app = Fastify({ logger: false });
    await registerObserverRoutes(app, service);
    expect(service.snapshot().threads.some((thread) => thread.id === "thread-one")).toBe(false);
    const excludedDetail = await app.inject({
      method: "GET",
      url: "/api/observer/threads/thread-one",
    });
    expect(excludedDetail.statusCode).toBe(404);
    expect(excludedDetail.headers["cache-control"]).toBe("no-store");
    expect(
      (
        await app.inject({
          method: "PUT",
          url: "/api/tasks/not%20valid/threads/thread-one",
        })
      ).statusCode,
    ).toBe(400);
  });
});
