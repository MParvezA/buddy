// @vitest-environment node
import { afterEach, describe, expect, it } from "vitest";
import type { FastifyInstance } from "fastify";
import { buildApp } from "../../../src/server/app.js";

let app: FastifyInstance | undefined;
afterEach(async () => {
  await app?.close();
  app = undefined;
});

describe("report routes", () => {
  it("generates manual immutable snapshots and lists history newest first", async () => {
    app = await buildApp({
      serveStatic: false,
      databasePath: ":memory:",
      observer: false,
      clock: () => new Date("2026-07-29T12:00:00.000Z"),
    });
    const first = await app.inject({ method: "POST", url: "/api/reports", payload: {} });
    const second = await app.inject({ method: "POST", url: "/api/reports", payload: {} });
    expect(first.statusCode).toBe(201);
    expect(second.statusCode).toBe(201);
    const history = await app.inject({ method: "GET", url: "/api/reports" });
    expect(history.json()).toHaveLength(2);
    expect(history.json()[0].sequence).toBe(2);
    const detail = await app.inject({
      method: "GET",
      url: `/api/reports/${first.json().id}`,
    });
    expect(detail.json().sequence).toBe(1);
  });

  it("persists valid settings and rejects invalid timezone without losing defaults", async () => {
    app = await buildApp({
      serveStatic: false,
      databasePath: ":memory:",
      observer: false,
      clock: () => new Date("2026-07-29T12:00:00.000Z"),
    });
    const invalid = await app.inject({
      method: "PUT",
      url: "/api/report-settings",
      payload: { time: "18:00", timezone: "Bad/Zone", narrativeEnabled: true },
    });
    expect(invalid.statusCode).toBe(400);
    const current = await app.inject({ method: "GET", url: "/api/report-settings" });
    expect(current.json().schedule).toEqual({
      time: "18:00",
      timezone: "Europe/Berlin",
      narrativeEnabled: false,
    });
    const valid = await app.inject({
      method: "PUT",
      url: "/api/report-settings",
      payload: { time: "19:15", timezone: "America/New_York", narrativeEnabled: false },
    });
    expect(valid.statusCode).toBe(200);
    expect(valid.json().schedule.time).toBe("19:15");
  });

  it("returns committed facts when optional Codex narrative is unavailable", async () => {
    app = await buildApp({
      serveStatic: false,
      databasePath: ":memory:",
      observer: false,
      clock: () => new Date("2026-07-29T12:00:00.000Z"),
    });
    await app.inject({
      method: "PUT",
      url: "/api/report-settings",
      payload: {
        time: "18:00",
        timezone: "Europe/Berlin",
        narrativeEnabled: true,
      },
    });
    const generated = await app.inject({
      method: "POST",
      url: "/api/reports",
      payload: {},
    });
    expect(generated.statusCode).toBe(201);
    expect(generated.json()).toMatchObject({
      factualDigest: { localDate: "2026-07-29" },
      narrative: { status: "failed" },
    });
    const retry = await app.inject({
      method: "POST",
      url: `/api/reports/${generated.json().id}/narrative`,
      payload: {},
    });
    expect(retry.statusCode).toBe(200);
    const conflicting = await app.inject({
      method: "POST",
      url: `/api/reports/${generated.json().id}/narrative`,
      payload: {},
    });
    // The disconnected retry fails open again and therefore remains retryable.
    expect(conflicting.statusCode).toBe(200);
  });

  it("returns conflict when retrying an already ready narrative", async () => {
    app = await buildApp({
      serveStatic: false,
      databasePath: ":memory:",
      observer: false,
      clock: () => new Date("2026-07-29T12:00:00.000Z"),
      reportNarrativeProvider: {
        generate: async (input) => ({
          reportingThreadId: "reporter",
          text: "Ready narrative",
          suggestions: input.digest.planned.map((task) => ({
            taskId: task.taskId,
            reason: "Generated suggestion",
            sourceThreadIds: task.threadIds,
          })),
        }),
      },
    });
    await app.inject({
      method: "PUT",
      url: "/api/report-settings",
      payload: {
        time: "18:00",
        timezone: "Europe/Berlin",
        narrativeEnabled: true,
      },
    });
    const generated = await app.inject({
      method: "POST",
      url: "/api/reports",
      payload: {},
    });
    expect(generated.json().narrative.status).toBe("ready");
    const retry = await app.inject({
      method: "POST",
      url: `/api/reports/${generated.json().id}/narrative`,
      payload: {},
    });
    expect(retry.statusCode).toBe(409);
    expect(retry.json()).toMatchObject({
      error: { code: "conflict", message: expect.stringMatching(/already ready/) },
    });
  });
});
