// @vitest-environment node
import Fastify, { type FastifyInstance } from "fastify";
import { afterEach, describe, expect, it } from "vitest";
import { registerAttentionRoutes } from "../../../src/server/attention/attention-routes.js";
import { AttentionRepository } from "../../../src/server/attention/attention-repository.js";
import { AttentionService } from "../../../src/server/attention/attention-service.js";
import { ObserverService } from "../../../src/server/codex/observer-service.js";
import {
  openDatabase,
  type PlanningDatabase,
} from "../../../src/server/storage/database.js";
import { ObserverRepository } from "../../../src/server/storage/observer-repository.js";
import type { ObservedThread } from "../../../src/shared/observer-types.js";

const now = "2026-07-29T12:00:00.000Z";
const thread: ObservedThread = {
  id: "thread-one",
  sessionId: "session-one",
  title: "Observed chat",
  cwd: "/workspace",
  source: "cli",
  cliVersion: "0.146.0",
  createdAt: now,
  updatedAt: now,
  recencyAt: now,
  archived: false,
  lastObservedAt: now,
  runtime: "active",
  waitingOnApproval: false,
  waitingOnUserInput: false,
  lastActivityAt: now,
};

let app: FastifyInstance | undefined;
let database: PlanningDatabase | undefined;
let observer: ObserverService | undefined;
let attention: AttentionService | undefined;

afterEach(async () => {
  attention?.stop();
  await observer?.stop();
  await app?.close();
  database?.close();
  app = undefined;
  database = undefined;
  observer = undefined;
  attention = undefined;
});

describe("attention routes", () => {
  it("serves capability state and persists acknowledge/dismiss without starting Codex", async () => {
    database = openDatabase({ path: ":memory:" });
    const observerRepository = new ObserverRepository(database.connection);
    observerRepository.upsertThread(thread);
    const attentionRepository = new AttentionRepository(database.connection);
    for (const [sourceKey, kind] of [
      ["turn:thread-one:failed", "failed_turn"],
      ["goal:thread-one:blocked", "explicit_blocker"],
    ] as const) {
      attentionRepository.upsert(
        {
          sourceKey,
          threadId: thread.id,
          turnId: null,
          itemId: null,
          kind,
          certainty: "explicit",
          sourceOccurredAt: now,
          sourceLabel: kind === "failed_turn" ? "Turn failed" : "Explicit blocker",
        },
        now,
      );
    }
    let processStarts = 0;
    observer = new ObserverService({
      repository: observerRepository,
      mode: "standalone_history",
      processFactory: () => {
        processStarts += 1;
        throw new Error("Codex transport must not start for local queue actions.");
      },
    });
    attention = new AttentionService({
      repository: attentionRepository,
      observer,
      clock: () => new Date(now),
      sweepIntervalMs: 60_000,
    });
    attention.start();
    app = Fastify();
    await registerAttentionRoutes(app, attention);

    const initial = await app.inject({ method: "GET", url: "/api/attention" });
    expect(initial.json()).toMatchObject({
      capability: "standalone_history",
      connectionState: "disconnected",
      liveRequestCoverage: "external_clients_unavailable",
    });
    const [first, second] = initial.json().items as Array<{ id: string }>;
    expect(
      (
        await app.inject({
          method: "POST",
          url: `/api/attention/${encodeURIComponent(first.id)}/acknowledge`,
        })
      ).json().items,
    ).toHaveLength(1);
    expect(
      (
        await app.inject({
          method: "POST",
          url: `/api/attention/${encodeURIComponent(second.id)}/dismiss`,
        })
      ).json().items,
    ).toEqual([]);
    expect(attentionRepository.find(first.id)?.lifecycle).toBe("acknowledged");
    expect(attentionRepository.find(second.id)?.lifecycle).toBe("dismissed");
    const history = await app.inject({
      method: "GET",
      url: "/api/attention/threads/thread-one",
    });
    expect(history.json().map((item: { lifecycle: string }) => item.lifecycle).sort())
      .toEqual(["acknowledged", "dismissed"]);
    expect(
      (
        await app.inject({
          method: "POST",
          url: `/api/attention/${encodeURIComponent(first.id)}/dismiss`,
        })
      ).statusCode,
    ).toBe(409);
    expect(attentionRepository.find(first.id)?.lifecycle).toBe("acknowledged");
    expect(processStarts).toBe(0);
  });

  it("validates IDs and reports missing local items", async () => {
    database = openDatabase({ path: ":memory:" });
    observer = new ObserverService({
      repository: new ObserverRepository(database.connection),
    });
    attention = new AttentionService({
      repository: new AttentionRepository(database.connection),
      observer,
    });
    app = Fastify();
    await registerAttentionRoutes(app, attention);
    expect(
      (
        await app.inject({
          method: "POST",
          url: "/api/attention/not-found/acknowledge",
        })
      ).statusCode,
    ).toBe(404);
    expect(
      (
        await app.inject({
          method: "POST",
          url: `/api/attention/${encodeURIComponent("\u0001")}/dismiss`,
        })
      ).statusCode,
    ).toBe(400);
  });
});
