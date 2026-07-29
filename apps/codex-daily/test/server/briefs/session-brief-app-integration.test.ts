// @vitest-environment node
import { spawn } from "node:child_process";
import { existsSync, mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { afterEach, describe, expect, it, vi } from "vitest";
import { buildApp } from "../../../src/server/app.js";

const fixture = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../../fixtures/fake-codex-app-server.py",
);

let temporaryDirectory: string | undefined;
let app: Awaited<ReturnType<typeof buildApp>> | undefined;

afterEach(async () => {
  await app?.close();
  if (temporaryDirectory) rmSync(temporaryDirectory, { recursive: true, force: true });
  app = undefined;
  temporaryDirectory = undefined;
});

describe("session brief application workflow", () => {
  it("updates API state in the background while retaining only validated structure", async () => {
    temporaryDirectory = mkdtempSync(path.join(tmpdir(), "codex-daily-app-brief-"));
    const databasePath = path.join(temporaryDirectory, "daily.sqlite");
    const requestLog = path.join(temporaryDirectory, "requests.jsonl");
    const methodLog = path.join(temporaryDirectory, "methods.txt");
    app = await buildApp({
      serveStatic: false,
      databasePath,
      observer: true,
      codexExecutable: fixture,
      processFactory: (executable, args) =>
        spawn(executable, [...args], {
          shell: false,
          stdio: ["pipe", "pipe", "pipe"],
          env: {
            ...process.env,
            CODEX_DAILY_FAKE_ANALYSIS_MODE: "source_changed",
            CODEX_DAILY_FAKE_REQUEST_LOG: requestLog,
            CODEX_DAILY_FAKE_METHOD_LOG: methodLog,
          },
        }),
      observerInventoryIntervalMs: 60_000,
      observerRequestTimeoutMs: 2_000,
      sessionBriefDebounceMs: 0,
      sessionBriefTurnTimeoutMs: 2_000,
    });

    await vi.waitFor(async () => {
      const response = await app!.inject({
        method: "GET",
        url: "/api/session-briefs",
        headers: { host: "127.0.0.1:4317" },
      });
      const body = response.json();
      expect(body).toMatchObject({
        total: 2,
        ready: 2,
        queued: 0,
        analyzing: 0,
      });
    }, { timeout: 3_000 });

    const briefs = await app.inject({
      method: "GET",
      url: "/api/session-briefs",
      headers: { host: "127.0.0.1:4317" },
    });
    expect(briefs.headers["cache-control"]).toBe("no-store");
    expect(briefs.json().items).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          analysisStatus: "ready",
          freshness: "current",
          lastGood: expect.objectContaining({
            generator: "codex_app_server",
            modelId: "gpt-5.6-sol",
          }),
        }),
      ]),
    );
    expect(
      briefs.json().items.find(
        (item: { threadId: string }) => item.threadId === "thread-one",
      ),
    ).toMatchObject({
      targetUpdatedAt: "2026-07-29T10:05:00.000Z",
      lastGood: { sourceUpdatedAt: "2026-07-29T10:05:00.000Z" },
    });
    const exported = await app.inject({
      method: "GET",
      url: "/api/operations/export",
      headers: { host: "127.0.0.1:4317" },
    });
    const diagnostics = await app.inject({
      method: "GET",
      url: "/api/operations/diagnostics",
      headers: { host: "127.0.0.1:4317" },
    });
    const retained = [
      JSON.stringify(briefs.json()),
      JSON.stringify(exported.json()),
      JSON.stringify(diagnostics.json()),
      readFileSync(requestLog, "utf8"),
      readFileSync(databasePath).toString("utf8"),
      existsSync(`${databasePath}-wal`)
        ? readFileSync(`${databasePath}-wal`).toString("utf8")
        : "",
    ].join("\n");
    expect(retained).not.toMatch(
      /SYNTHETIC_SOURCE_SECRET|SYNTHETIC_REASONING_SECRET|STRUCTURED_TOKEN_MUST_DROP|unsupported\.png/,
    );

    const methods = readFileSync(methodLog, "utf8").trim().split("\n");
    expect(methods.filter((method) => method === "thread/read")).toHaveLength(3);
    expect(methods.filter((method) => method === "thread/start")).toHaveLength(2);
    expect(methods.filter((method) => method === "turn/start")).toHaveLength(2);
    expect(methods).not.toEqual(
      expect.arrayContaining([
        "thread/archive",
        "turn/interrupt",
        "item/commandExecution/requestApproval",
      ]),
    );
  });

  it.each([
    {
      name: "delete-day",
      url: "/api/operations/days/2026-07-29",
      confirmation: "DELETE 2026-07-29",
    },
    {
      name: "delete-all",
      url: "/api/operations/data",
      confirmation: "DELETE ALL CODEX DAILY DATA",
    },
  ])("blocks late brief promotion across $name maintenance", async (operation) => {
    temporaryDirectory = mkdtempSync(path.join(tmpdir(), "codex-daily-delete-brief-"));
    const databasePath = path.join(temporaryDirectory, "daily.sqlite");
    let abortedAttempts = 0;
    const analyzer = {
      analyze: vi.fn(
        ({ signal }: { signal?: AbortSignal }) =>
          new Promise<{
            content: {
              currentState: string;
              done: string[];
              operatorActions: string[];
              blockers: string[];
              confidence: "high";
              evidence: string[];
            };
            generator: "codex_app_server";
            modelId: "gpt-5.6-sol";
          }>((resolve) => {
            signal?.addEventListener(
              "abort",
              () => {
                abortedAttempts += 1;
                resolve({
                  content: {
                    currentState: "This obsolete result must not be promoted.",
                    done: [],
                    operatorActions: [],
                    blockers: [],
                    confidence: "high",
                    evidence: ["user:first-intent"],
                  },
                  generator: "codex_app_server",
                  modelId: "gpt-5.6-sol",
                });
              },
              { once: true },
            );
          }),
      ),
    };
    app = await buildApp({
      serveStatic: false,
      databasePath,
      observer: true,
      codexExecutable: fixture,
      observerInventoryIntervalMs: 60_000,
      observerRequestTimeoutMs: 2_000,
      sessionBriefAnalyzer: analyzer,
      sessionBriefDebounceMs: 0,
    });
    await vi.waitFor(async () => {
      const response = await app!.inject({
        method: "GET",
        url: "/api/session-briefs",
        headers: { host: "127.0.0.1:4317" },
      });
      expect(response.json().analyzing).toBe(2);
    });

    const deletion = await app.inject({
      method: "DELETE",
      url: operation.url,
      headers: { host: "127.0.0.1:4317" },
      payload: { confirmation: operation.confirmation },
    });
    expect(deletion.statusCode).toBe(200);
    expect(abortedAttempts).toBe(2);

    const exported = await app.inject({
      method: "GET",
      url: "/api/operations/export",
      headers: { host: "127.0.0.1:4317" },
    });
    expect(exported.json().sessionBriefs).toEqual([]);
    expect(JSON.stringify(exported.json())).not.toContain(
      "This obsolete result must not be promoted.",
    );
  });
});
