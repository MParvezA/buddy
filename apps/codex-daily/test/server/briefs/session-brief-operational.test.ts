// @vitest-environment node
import { EventEmitter } from "node:events";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { SessionBriefAnalyzer } from "../../../src/server/briefs/session-brief-analyzer.js";
import { SessionBriefRepository } from "../../../src/server/briefs/session-brief-repository.js";
import { SessionBriefService } from "../../../src/server/briefs/session-brief-service.js";
import {
  openDatabase,
  type PlanningDatabase,
} from "../../../src/server/storage/database.js";
import { ObserverRepository } from "../../../src/server/storage/observer-repository.js";
import type {
  ObservedThread,
  ObserverSnapshot,
} from "../../../src/shared/observer-types.js";

let database: PlanningDatabase | undefined;

afterEach(() => {
  vi.useRealTimers();
  database?.close();
  database = undefined;
});

function observedThread(updatedAt = "2026-07-29T20:00:00.000Z"): ObservedThread {
  return {
    id: "synthetic-thread",
    sessionId: "synthetic-session",
    title: "Invented release monitor",
    cwd: "/invented/workspace",
    source: "cli",
    cliVersion: "synthetic",
    createdAt: updatedAt,
    updatedAt,
    recencyAt: updatedAt,
    archived: false,
    lastObservedAt: updatedAt,
    runtime: "idle",
    waitingOnApproval: false,
    waitingOnUserInput: false,
    lastActivityAt: null,
  };
}

function observerSnapshot(
  threads: ObservedThread[],
  connected = true,
): ObserverSnapshot {
  return {
    health: {
      state: connected ? "connected" : "disconnected",
      capability: "standalone_history",
      lastSuccessfulSyncAt: connected ? "2026-07-29T20:00:00.000Z" : null,
      lastInventoryRefreshAt: connected ? "2026-07-29T20:00:00.000Z" : null,
      diagnostic: null,
    },
    threads,
    activities: [],
    taskLinks: [],
  };
}

class FakeObserver extends EventEmitter {
  constructor(private value: ObserverSnapshot) {
    super();
  }
  snapshot() {
    return this.value;
  }
  update(value: ObserverSnapshot) {
    this.value = value;
    this.emit("snapshot", { id: "synthetic", snapshot: value });
  }
}

const result = {
  content: {
    currentState: "The invented chat is preparing a release checklist.",
    done: ["The chat reports the checklist draft is complete."],
    operatorActions: ["Review the invented dates."],
    blockers: [],
    confidence: "high" as const,
    evidence: ["user:first-intent"],
  },
  generator: "codex_app_server" as const,
  modelId: "gpt-5.6-sol" as const,
};

async function flush() {
  for (let index = 0; index < 8; index += 1) await Promise.resolve();
}

describe("session brief operational lifecycle", () => {
  it("reports restart recovery and bounded drain without exposing job content", async () => {
    database = openDatabase({ path: ":memory:" });
    const thread = observedThread();
    new ObserverRepository(database.connection).upsertThread(thread);
    const repository = new SessionBriefRepository(database.connection, () => "job");
    const orphan = repository.enqueue(
      thread.id,
      thread.updatedAt,
      "automatic",
      "2026-07-29T20:00:00.000Z",
    )!;
    repository.markAnalyzing(orphan.jobId, "2026-07-29T20:00:01.000Z");
    const observer = new FakeObserver(observerSnapshot([thread], false));
    const analyzer: SessionBriefAnalyzer = {
      analyze: ({ signal }) =>
        new Promise((resolve) => {
          signal?.addEventListener("abort", () => resolve(result), { once: true });
        }),
    };
    const service = new SessionBriefService({
      repository,
      observer,
      analyzer,
      clock: () => new Date("2026-07-29T20:02:00.000Z"),
      debounceMs: 0,
      retentionIntervalMs: 60_000,
    });

    service.start();
    expect(service.operationalDiagnostics()).toMatchObject({
      selectedRecentSessions: 1,
      queued: 1,
      analyzing: 0,
      configuredWorkerConcurrency: 2,
      activeWorkerCount: 0,
      orphanJobsRecoveredAtStartup: 1,
      shutdownState: "running",
    });
    observer.update(observerSnapshot([thread]));
    await flush();
    expect(service.operationalDiagnostics()).toMatchObject({
      analyzing: 1,
      activeWorkerCount: 1,
      observedPeakWorkerConcurrency: 1,
    });
    await service.stop();
    expect(service.operationalDiagnostics()).toMatchObject({
      analyzing: 1,
      activeWorkerCount: 0,
      shutdownState: "stopped",
    });
    expect(repository.listBriefRowsForExport()).toEqual([]);
  });

  it("retains last-good overnight and prunes at the exact 24-hour boundary", async () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-07-29T20:00:00.000Z"));
    database = openDatabase({ path: ":memory:" });
    const thread = observedThread();
    new ObserverRepository(database.connection).upsertThread(thread);
    const repository = new SessionBriefRepository(database.connection);
    const observer = new FakeObserver(observerSnapshot([thread]));
    const service = new SessionBriefService({
      repository,
      observer,
      analyzer: { analyze: vi.fn(async () => result) },
      clock: () => new Date(Date.now()),
      debounceMs: 0,
      retentionIntervalMs: 60 * 60 * 1_000,
    });

    service.start();
    await vi.advanceTimersByTimeAsync(0);
    await flush();
    expect(service.operationalDiagnostics()).toMatchObject({
      readyCurrent: 1,
      lastSuccessfulModelId: "gpt-5.6-sol",
      lastSuccessfulGenerationAt: "2026-07-29T20:00:00.000Z",
    });

    observer.update(observerSnapshot([]));
    expect(repository.listBriefRowsForExport()).toHaveLength(1);
    await vi.advanceTimersByTimeAsync(24 * 60 * 60 * 1_000 - 1);
    expect(repository.listBriefRowsForExport()).toHaveLength(1);
    await vi.advanceTimersByTimeAsync(1);
    expect(repository.listBriefRowsForExport()).toEqual([]);
    expect(service.operationalDiagnostics()).toMatchObject({
      lastPrunedRowCount: 1,
      lastPruneAt: "2026-07-30T20:00:00.000Z",
    });
    await service.stop();
  });
});
