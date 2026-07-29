// @vitest-environment node
import type { FastifyInstance } from "fastify";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { afterEach, describe, expect, it, vi } from "vitest";
import { buildApp } from "../../../src/server/app.js";

const fixture = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../../fixtures/fake-codex-app-server.py",
);
let app: FastifyInstance | undefined;
let temporaryDirectory: string | undefined;

afterEach(async () => {
  await app?.close();
  app = undefined;
  if (temporaryDirectory) rmSync(temporaryDirectory, { recursive: true, force: true });
  temporaryDirectory = undefined;
});

async function open(localDate: string, databasePath: string, observer: boolean) {
  return buildApp({
    serveStatic: false,
    observer,
    observerMode: "shared_live",
    codexExecutable: fixture,
    databasePath,
    clock: () => new Date(`${localDate}T10:00:00.000Z`),
    observerInventoryIntervalMs: 60_000,
    observerRequestTimeoutMs: 2_000,
    attentionSweepIntervalMs: 60_000,
  });
}

describe("morning-to-next-morning lifecycle", () => {
  it("persists intent, normalized work, attention, report, and restart without duplicates", async () => {
    temporaryDirectory = mkdtempSync(path.join(tmpdir(), "codex-daily-lifecycle-"));
    const databasePath = path.join(temporaryDirectory, "daily.sqlite");

    app = await open("2026-07-28", databasePath, false);
    const prior = await app.inject({
      method: "POST",
      url: "/api/planning/2026-07-28/tasks",
      payload: { title: "Finish observer hardening" },
    });
    const priorTaskId = prior.json().tasks[0].id as string;
    await app.close();

    app = await open("2026-07-29", databasePath, true);
    const morning = await app.inject({
      method: "GET",
      url: "/api/planning?date=2026-07-29",
    });
    expect(morning.json()).toMatchObject({
      reviewRequired: true,
      priorDay: { unresolvedTasks: [{ id: priorTaskId }] },
    });
    const carried = await app.inject({
      method: "POST",
      url: `/api/planning/2026-07-29/review/${priorTaskId}`,
      payload: { action: "carry_forward" },
    });
    const taskId = carried.json().tasks[0].id as string;

    await vi.waitFor(
      async () => {
        const observer = await app!.inject({ method: "GET", url: "/api/observer" });
        expect(observer.json().health.state).toBe("connected");
        expect(observer.json().activities.length).toBeGreaterThan(0);
      },
      { timeout: 3_000 },
    );
    const linked = await app.inject({
      method: "PUT",
      url: `/api/tasks/${taskId}/threads/thread-one`,
    });
    expect(linked.statusCode).toBe(200);
    await vi.waitFor(
      async () => {
        const attention = await app!.inject({ method: "GET", url: "/api/attention" });
        expect(attention.json().items.length).toBeGreaterThan(0);
      },
      { timeout: 3_000 },
    );
    const attention = await app.inject({ method: "GET", url: "/api/attention" });
    const attentionId = attention.json().items[0].id as string;
    expect(
      (
        await app.inject({
          method: "POST",
          url: `/api/attention/${encodeURIComponent(attentionId)}/acknowledge`,
        })
      ).statusCode,
    ).toBe(200);
    await app.inject({
      method: "PUT",
      url: "/api/report-settings",
      payload: {
        time: "18:00",
        timezone: "Europe/Berlin",
        narrativeEnabled: true,
      },
    });
    const report = await app.inject({
      method: "POST",
      url: "/api/reports",
      payload: { localDate: "2026-07-29" },
    });
    expect(report.statusCode).toBe(201);
    expect(report.json()).toMatchObject({
      localDate: "2026-07-29",
      narrative: { status: "ready" },
    });
    const beforeRestart = await app.inject({
      method: "GET",
      url: "/api/operations/export",
    });
    const activityCount = beforeRestart.json().activities.length as number;
    await app.close();

    app = await open("2026-07-30", databasePath, true);
    await vi.waitFor(
      async () => {
        const observer = await app!.inject({ method: "GET", url: "/api/observer" });
        expect(observer.json().health.state).toBe("connected");
      },
      { timeout: 3_000 },
    );
    const nextMorning = await app.inject({
      method: "GET",
      url: "/api/planning?date=2026-07-30",
    });
    expect(nextMorning.json()).toMatchObject({
      reviewRequired: true,
      priorDay: { unresolvedTasks: [{ id: taskId }] },
    });
    const afterRestart = await app.inject({
      method: "GET",
      url: "/api/operations/export",
    });
    expect(afterRestart.json().activities).toHaveLength(activityCount);
    expect(afterRestart.json().taskLinks).toHaveLength(1);
    expect(afterRestart.json().reports).toHaveLength(1);
  });
});

