// @vitest-environment node
import type { FastifyInstance } from "fastify";
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { spawn } from "node:child_process";
import { afterEach, describe, expect, it, vi } from "vitest";
import { buildApp } from "../../../src/server/app.js";

let app: FastifyInstance | undefined;
let temporaryDirectory: string | undefined;
const fixture = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../../fixtures/fake-codex-app-server.py",
);

afterEach(async () => {
  await app?.close();
  app = undefined;
  if (temporaryDirectory) rmSync(temporaryDirectory, { recursive: true, force: true });
  temporaryDirectory = undefined;
});

describe("privacy and diagnostics routes", () => {
  it("serves redacted health/export and requires exact destructive confirmation", async () => {
    app = await buildApp({
      serveStatic: false,
      observer: false,
      databasePath: ":memory:",
      clock: () => new Date("2026-07-29T08:00:00.000Z"),
    });
    await app.inject({
      method: "POST",
      url: "/api/planning/2026-07-29/tasks",
      payload: { title: "Ship local monitor" },
    });

    const diagnostics = await app.inject({
      method: "GET",
      url: "/api/operations/diagnostics",
    });
    expect(diagnostics.statusCode).toBe(200);
    expect(diagnostics.json()).toMatchObject({
      localOnly: true,
      dataLocation: "Temporary in-memory database",
      database: { status: "ok", foreignKeyViolations: 0 },
      runtime: { application: "codex-daily" },
    });

    const exported = await app.inject({
      method: "GET",
      url: "/api/operations/export",
    });
    expect(exported.headers["content-disposition"]).toContain(
      "codex-daily-export.json",
    );
    expect(exported.json()).toMatchObject({
      product: "codex-daily",
      tasks: [{ title: "Ship local monitor" }],
    });
    expect(exported.body).not.toMatch(/transcript|credential|raw App Server/i);

    const refused = await app.inject({
      method: "DELETE",
      url: "/api/operations/days/2026-07-29",
      payload: { confirmation: "yes" },
    });
    expect(refused.statusCode).toBe(400);

    const deleted = await app.inject({
      method: "DELETE",
      url: "/api/operations/days/2026-07-29",
      payload: { confirmation: "DELETE 2026-07-29" },
    });
    expect(deleted.statusCode).toBe(200);
    expect(deleted.json()).toMatchObject({
      scope: "day",
      codexHistoryChanged: false,
    });
    const planning = await app.inject({
      method: "GET",
      url: "/api/planning?date=2026-07-29",
    });
    expect(planning.json().tasks).toEqual([]);
  });

  it("sends zero ordinary-thread mutation methods while coordinated deletion pauses monitoring", async () => {
    temporaryDirectory = mkdtempSync(path.join(tmpdir(), "codex-daily-methods-"));
    const methodLog = path.join(temporaryDirectory, "methods.log");
    app = await buildApp({
      serveStatic: false,
      observer: true,
      observerMode: "shared_live",
      codexExecutable: fixture,
      databasePath: ":memory:",
      clock: () => new Date("2026-07-29T08:00:00.000Z"),
      observerInventoryIntervalMs: 60_000,
      observerRequestTimeoutMs: 2_000,
      processFactory: (executable, args) =>
        spawn(executable, [...args], {
          shell: false,
          stdio: ["pipe", "pipe", "pipe"],
          env: {
            ...process.env,
            CODEX_DAILY_FAKE_METHOD_LOG: methodLog,
          },
        }),
    });
    await vi.waitFor(async () => {
      const health = await app!.inject({ method: "GET", url: "/api/health" });
      expect(health.json().connection.state).toBe("connected");
    });

    const deleted = await app.inject({
      method: "DELETE",
      url: "/api/operations/data",
      payload: { confirmation: "DELETE ALL CODEX DAILY DATA" },
    });
    expect(deleted.statusCode).toBe(200);
    await vi.waitFor(async () => {
      const health = await app!.inject({ method: "GET", url: "/api/health" });
      expect(["connecting", "connected"]).toContain(
        health.json().connection.state,
      );
    });
    await app.close();
    app = undefined;

    const methods = readFileSync(methodLog, "utf8").trim().split("\n");
    expect(methods).toEqual(
      expect.arrayContaining(["initialize", "initialized", "thread/list"]),
    );
    expect(methods).not.toEqual(
      expect.arrayContaining([
        "turn/start",
        "thread/archive",
        "thread/unarchive",
        "thread/delete",
        "serverRequest/respond",
        "item/commandExecution/approve",
      ]),
    );
  });
});
