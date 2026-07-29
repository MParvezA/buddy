// @vitest-environment node
import Fastify from "fastify";
import { EventEmitter } from "node:events";
import { afterEach, describe, expect, it } from "vitest";
import { registerSessionBriefRoutes } from "../../../src/server/briefs/session-brief-routes.js";
import {
  SessionBriefNotFoundError,
  SessionBriefNotSelectedError,
  SessionBriefObserverUnavailableError,
  type SessionBriefService,
} from "../../../src/server/briefs/session-brief-service.js";
import type { SessionBriefSnapshot } from "../../../src/shared/session-briefs.js";

const empty: SessionBriefSnapshot = {
  observer: { state: "connected", capability: "standalone_history" },
  selectedAt: "2026-07-29T12:00:00.000Z",
  items: [],
  total: 0,
  queued: 0,
  analyzing: 0,
  ready: 0,
  stale: 0,
  unavailable: 0,
  failed: 0,
};

class FakeBriefs extends EventEmitter {
  failure: Error | null = null;
  snapshot() {
    return empty;
  }
  nextEvent() {
    return { id: "1", snapshot: empty };
  }
  refreshAll() {
    if (this.failure) throw this.failure;
    return empty;
  }
  refresh(threadId: string) {
    void threadId;
    if (this.failure) throw this.failure;
    return empty;
  }
}

const apps: Array<ReturnType<typeof Fastify>> = [];

afterEach(async () => {
  await Promise.all(apps.splice(0).map((app) => app.close()));
});

async function setup() {
  const app = Fastify();
  apps.push(app);
  const briefs = new FakeBriefs();
  await registerSessionBriefRoutes(
    app,
    briefs as unknown as SessionBriefService,
    50,
  );
  return { app, briefs };
}

describe("session brief routes", () => {
  it("returns authoritative no-store snapshots and accepted refresh intent", async () => {
    const { app } = await setup();
    const read = await app.inject({ method: "GET", url: "/api/session-briefs" });
    expect(read.statusCode).toBe(200);
    expect(read.headers["cache-control"]).toBe("no-store");
    expect(read.json()).toEqual(empty);

    const refresh = await app.inject({
      method: "POST",
      url: "/api/session-briefs/refresh",
    });
    expect(refresh.statusCode).toBe(202);
    expect(refresh.headers["cache-control"]).toBe("no-store");
  });

  it.each([
    [new SessionBriefNotFoundError("missing"), 404, "not_found"],
    [new SessionBriefNotSelectedError("outside"), 409, "not_selected"],
    [
      new SessionBriefObserverUnavailableError("offline"),
      503,
      "observer_unavailable",
    ],
  ])("maps safe refresh failures", async (failure, status, code) => {
    const { app, briefs } = await setup();
    briefs.failure = failure;
    const response = await app.inject({
      method: "POST",
      url: "/api/session-briefs/thread-one/refresh",
    });
    expect(response.statusCode).toBe(status);
    expect(response.json()).toEqual({
      error: { code, message: failure.message },
    });
  });

  it("rejects invalid thread IDs before service access", async () => {
    const { app } = await setup();
    const response = await app.inject({
      method: "POST",
      url: "/api/session-briefs/not%20safe/refresh",
    });
    expect(response.statusCode).toBe(400);
    expect(response.json().error.code).toBe("validation");
  });
});
