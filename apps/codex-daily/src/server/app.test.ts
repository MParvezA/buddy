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
    app = await buildApp({ serveStatic: false });

    const health = await app.inject({ method: "GET", url: "/api/health" });
    const day = await app.inject({ method: "GET", url: "/api/day" });

    expect(health.statusCode).toBe(200);
    expect(health.json<HealthResponse>()).toEqual({
      service: "codex-daily",
      status: "ok",
      mode: "representative",
      connection: "not-connected",
    });
    expect(day.statusCode).toBe(200);
    expect(day.json<DashboardSnapshot>()).toMatchObject({
      mode: "representative",
      date: "2026-07-29",
      connection: { state: "not-connected" },
    });
    expect(day.json<DashboardSnapshot>().attention.map((item) => item.kind)).toEqual([
      "approval",
      "question",
      "failure",
      "interruption",
      "blocker",
      "possibly-stale",
    ]);
  });

  it("exposes only read endpoints", async () => {
    app = await buildApp({ serveStatic: false });

    const response = await app.inject({ method: "POST", url: "/api/day" });

    expect(response.statusCode).toBe(404);
  });
});
