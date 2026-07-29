// @vitest-environment node
import { afterEach, describe, expect, it } from "vitest";
import type { FastifyInstance } from "fastify";
import type { DashboardSnapshot, HealthResponse } from "../shared/dashboard.js";
import { buildApp } from "./app.js";

let app: FastifyInstance | undefined;

afterEach(async () => {
  await app?.close();
  app = undefined;
});

describe("local service", () => {
  it("returns deterministic representative health and day contracts", async () => {
    app = await buildApp({ serveStatic: false, databasePath: ":memory:" });

    const health = await app.inject({ method: "GET", url: "/api/health" });
    const day = await app.inject({ method: "GET", url: "/api/day" });

    expect(health.statusCode).toBe(200);
    expect(health.json<HealthResponse>()).toEqual({
      service: "codex-daily",
      status: "ok",
      mode: "observer",
      connection: {
        state: "disconnected",
        capability: "standalone_history",
        diagnostic: null,
      },
    });
    expect(day.statusCode).toBe(200);
    expect(day.json<DashboardSnapshot>()).toMatchObject({
      mode: "representative",
      date: "2026-07-29",
      connection: { state: "not-connected" },
    });
    const attention = await app.inject({ method: "GET", url: "/api/attention" });
    expect(attention.json()).toMatchObject({
      capability: "standalone_history",
      liveRequestCoverage: "external_clients_unavailable",
      items: [],
    });
  });

  it("adds an empty durable planning resource without changing representative monitoring", async () => {
    app = await buildApp({
      serveStatic: false,
      databasePath: ":memory:",
      clock: () => new Date("2026-07-29T12:00:00.000Z"),
    });

    const planning = await app.inject({ method: "GET", url: "/api/planning" });
    const unsupported = await app.inject({ method: "POST", url: "/api/day" });

    expect(planning.statusCode).toBe(200);
    expect(planning.json()).toMatchObject({
      localDate: "2026-07-29",
      timezone: "Europe/Berlin",
      reviewRequired: false,
      tasks: [],
    });
    expect(unsupported.statusCode).toBe(404);
  });
});
