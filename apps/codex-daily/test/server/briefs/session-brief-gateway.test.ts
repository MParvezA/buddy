// @vitest-environment node
import { spawn } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { afterEach, describe, expect, it } from "vitest";
import {
  SessionBriefAnalysisError,
} from "../../../src/server/briefs/session-brief-analyzer.js";
import { SessionBriefGateway } from "../../../src/server/briefs/session-brief-gateway.js";
import { ObserverService } from "../../../src/server/codex/observer-service.js";
import { ObserverInternalTurnError } from "../../../src/server/codex/observer-service.js";
import {
  openDatabase,
  type PlanningDatabase,
} from "../../../src/server/storage/database.js";
import { ObserverRepository } from "../../../src/server/storage/observer-repository.js";

const fixture = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../../fixtures/fake-codex-app-server.py",
);

let database: PlanningDatabase | undefined;
let observer: ObserverService | undefined;
let temporaryDirectory: string | undefined;

afterEach(async () => {
  await observer?.stop();
  database?.close();
  if (temporaryDirectory) rmSync(temporaryDirectory, { recursive: true, force: true });
  observer = undefined;
  database = undefined;
  temporaryDirectory = undefined;
});

describe("GPT-5.6 session brief gateway", () => {
  it("uses the exact no-authority model contract and exact turn completion", async () => {
    temporaryDirectory = mkdtempSync(path.join(tmpdir(), "codex-daily-brief-"));
    const requestLog = path.join(temporaryDirectory, "requests.jsonl");
    database = openDatabase({ path: ":memory:" });
    const repository = new ObserverRepository(database.connection);
    observer = new ObserverService({
      repository,
      executable: fixture,
      processFactory: (executable, args) =>
        spawn(executable, [...args], {
          shell: false,
          stdio: ["pipe", "pipe", "pipe"],
          env: {
            ...process.env,
            CODEX_DAILY_FAKE_REQUEST_LOG: requestLog,
          },
        }),
      inventoryIntervalMs: 60_000,
      requestTimeoutMs: 2_000,
    });
    await observer.start();
    const result = await new SessionBriefGateway(observer, 2_000).analyze({
      threadId: "thread-one",
      sourceUpdatedAt: "2026-07-29T10:00:00.000Z",
    });

    expect(result).toMatchObject({
      generator: "codex_app_server",
      modelId: "gpt-5.6-sol",
      content: {
        currentState: "The chat is organizing the release.",
        confidence: "high",
      },
    });
    const requests = readFileSync(requestLog, "utf8")
      .trim()
      .split("\n")
      .map((line) => JSON.parse(line) as Record<string, unknown>);
    const start = requests.find((request) =>
      request.method === "thread/start" &&
      (request.params as Record<string, unknown>).ephemeral === true
    )!;
    expect(start.params).toEqual({
      model: "gpt-5.6-sol",
      allowProviderModelFallback: false,
      ephemeral: true,
      approvalPolicy: "never",
      dynamicTools: [],
      environments: [],
      runtimeWorkspaceRoots: [],
      cwd: null,
      experimentalRawEvents: false,
    });
    const turn = requests.find((request) =>
      request.method === "turn/start" &&
      String((request.params as Record<string, unknown>).threadId).startsWith(
        "codex-daily-analysis-",
      )
    )!;
    const turnParams = turn.params as Record<string, unknown>;
    expect(turnParams).toMatchObject({
      model: "gpt-5.6-sol",
      effort: "medium",
      environments: [],
      input: [{ type: "text", text: expect.any(String) }],
      outputSchema: {
        type: "object",
        additionalProperties: false,
      },
    });
    expect(Array.from(
      ((turnParams.input as Array<{ text: string }>)[0]?.text ?? ""),
    ).length).toBeLessThanOrEqual(32_000);
    expect(JSON.stringify(turnParams)).not.toMatch(
      /STRUCTURED_TOKEN_MUST_DROP|SYNTHETIC_REASONING_SECRET|unsupported\.png/,
    );
    expect(observer.snapshot().threads.map((item) => item.id)).not.toContain(
      "codex-daily-analysis-1",
    );
    expect(JSON.stringify(observer.snapshot())).not.toMatch(
      /SYNTHETIC_SOURCE_SECRET|SECRET RESPONSE|SYNTHETIC_REASONING_SECRET/,
    );
    expect(requests.map((request) => request.method)).not.toEqual(
      expect.arrayContaining([
        "thread/archive",
        "turn/interrupt",
        "item/commandExecution/requestApproval",
      ]),
    );
  });

  it("does not create an analysis thread when usable input is empty", async () => {
    const calls: string[] = [];
    const gateway = new SessionBriefGateway({
      readSessionBriefSource: async () => [
        { id: "one", items: [{ type: "reasoning", summary: "private" }] },
      ],
      createSessionBriefAnalysisThread: async () => {
        calls.push("thread/start");
        return "analysis";
      },
      runSessionBriefAnalysisTurn: async () => "{}",
    });
    await expect(
      gateway.analyze({
        threadId: "ordinary",
        sourceUpdatedAt: "2026-07-29T10:00:00.000Z",
      }),
    ).rejects.toMatchObject<Partial<SessionBriefAnalysisError>>({
      category: "empty_usable_content",
      transient: false,
    });
    expect(calls).toEqual([]);
  });

  it.each([
    [
      async () => {
        throw new ObserverInternalTurnError("timeout");
      },
      "timeout",
      true,
    ],
    [
      async () => {
        throw new ObserverInternalTurnError("refusal");
      },
      "refusal",
      false,
    ],
    [async () => "```json\n{}\n```", "invalid_output", false],
  ])("maps model boundaries to safe categories", async (run, category, transient) => {
    const gateway = new SessionBriefGateway({
      readSessionBriefSource: async () => [{
        id: "one",
        items: [{
          type: "userMessage",
          content: [{ type: "text", text: "Organize the release" }],
        }],
      }],
      createSessionBriefAnalysisThread: async () => "analysis",
      runSessionBriefAnalysisTurn: run,
    });
    await expect(
      gateway.analyze({
        threadId: "ordinary",
        sourceUpdatedAt: "2026-07-29T10:00:00.000Z",
      }),
    ).rejects.toMatchObject({ category, transient });
  });
});
