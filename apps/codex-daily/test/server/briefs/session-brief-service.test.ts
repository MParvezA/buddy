// @vitest-environment node
import { EventEmitter } from "node:events";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { SessionBriefAnalyzer } from "../../../src/server/briefs/session-brief-analyzer.js";
import { SessionBriefAnalysisError } from "../../../src/server/briefs/session-brief-analyzer.js";
import { SessionBriefRepository } from "../../../src/server/briefs/session-brief-repository.js";
import {
  selectRecentSessions,
  SessionBriefObserverUnavailableError,
  SessionBriefService,
} from "../../../src/server/briefs/session-brief-service.js";
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

function thread(id: string, updatedAt: string, archived = false): ObservedThread {
  return {
    id,
    sessionId: `session-${id}`,
    title: id,
    cwd: "/workspace",
    source: "cli",
    cliVersion: "1",
    createdAt: updatedAt,
    updatedAt,
    recencyAt: updatedAt,
    archived,
    lastObservedAt: updatedAt,
    runtime: "idle",
    waitingOnApproval: false,
    waitingOnUserInput: false,
    lastActivityAt: null,
  };
}

class FakeObserver extends EventEmitter {
  constructor(public value: ObserverSnapshot) {
    super();
  }
  snapshot() {
    return this.value;
  }
  update(value: ObserverSnapshot) {
    this.value = value;
    this.emit("snapshot", { id: "1", snapshot: value });
  }
}

function snapshot(
  threads: ObservedThread[],
  state: ObserverSnapshot["health"]["state"] = "connected",
): ObserverSnapshot {
  return {
    health: {
      state,
      capability: "standalone_history",
      lastSuccessfulSyncAt: state === "connected" ? "2026-07-29T12:00:00.000Z" : null,
      lastInventoryRefreshAt: state === "connected" ? "2026-07-29T12:00:00.000Z" : null,
      diagnostic: null,
    },
    threads,
    activities: [],
    taskLinks: [],
  };
}

async function settle() {
  await new Promise((resolve) => setTimeout(resolve, 0));
  await new Promise((resolve) => setTimeout(resolve, 0));
}

async function flushPromises() {
  for (let index = 0; index < 8; index += 1) await Promise.resolve();
}

const realResult = {
  content: {
    currentState: "The chat is organizing the release.",
    done: ["The chat reports the foundation is ready."],
    operatorActions: ["Review the release checklist."],
    blockers: [],
    confidence: "high" as const,
    evidence: ["user:first-intent"],
  },
  generator: "codex_app_server" as const,
  modelId: "gpt-5.6-sol" as const,
};

describe("session brief service", () => {
  it("selects literal recency with a deterministic tie-break and a ten-item cap", () => {
    const threads = Array.from({ length: 12 }, (_, index) =>
      thread(
        `thread-${String(index).padStart(2, "0")}`,
        index < 2
          ? "2026-07-29T12:00:00.000Z"
          : `2026-07-29T${String(11 - index).padStart(2, "0")}:00:00.000Z`,
        index === 11,
      ),
    );
    const selected = selectRecentSessions(threads);
    expect(selected).toHaveLength(10);
    expect(selected.slice(0, 2).map((item) => item.id)).toEqual([
      "thread-00",
      "thread-01",
    ]);
    expect(selected.some((item) => item.archived)).toBe(false);
  });

  it("waits for observer readiness, emits GPT results, and refreshes idempotently", async () => {
    database = openDatabase({ path: ":memory:" });
    const observed = thread("thread-one", "2026-07-29T10:00:00.000Z");
    new ObserverRepository(database.connection).upsertThread(observed);
    const observer = new FakeObserver(snapshot([observed], "disconnected"));
    const analyzer: SessionBriefAnalyzer = {
      analyze: async () => realResult,
    };
    const analyze = vi.spyOn(analyzer, "analyze");
    const service = new SessionBriefService({
      repository: new SessionBriefRepository(database.connection, () => "job-one"),
      observer,
      analyzer,
      clock: () => new Date("2026-07-29T12:00:00.000Z"),
      retentionIntervalMs: 100_000,
      debounceMs: 0,
    });
    service.start();
    expect(service.snapshot().items[0]).toMatchObject({
      analysisStatus: "unavailable",
      freshness: "missing",
      failure: { category: "observer_unavailable" },
    });
    expect(analyze).not.toHaveBeenCalled();
    expect(() => service.refreshAll()).toThrow(SessionBriefObserverUnavailableError);

    observer.update(snapshot([observed]));
    await settle();
    expect(analyze).toHaveBeenCalledWith(expect.objectContaining({
      threadId: "thread-one",
      sourceUpdatedAt: observed.updatedAt,
    }));
    expect(service.snapshot().items[0]).toMatchObject({
      analysisStatus: "ready",
      freshness: "current",
      lastGood: {
        generator: "codex_app_server",
        modelId: "gpt-5.6-sol",
      },
    });
    service.refresh("thread-one");
    service.refresh("thread-one");
    await settle();
    expect(analyze).toHaveBeenCalledTimes(2);
    await service.stop();
  });

  it("discards a superseded result without overwriting the newer revision", async () => {
    database = openDatabase({ path: ":memory:" });
    const first = thread("thread-one", "2026-07-29T10:00:00.000Z");
    const repository = new ObserverRepository(database.connection);
    repository.upsertThread(first);
    const observer = new FakeObserver(snapshot([first]));
    let resolveAnalysis:
      | ((value: Awaited<ReturnType<SessionBriefAnalyzer["analyze"]>>) => void)
      | undefined;
    let analysisCount = 0;
    const analyzer: SessionBriefAnalyzer = {
      analyze: () => {
        analysisCount += 1;
        return analysisCount === 1
          ? new Promise((resolve) => {
              resolveAnalysis = resolve;
            })
          : Promise.resolve(realResult);
      },
    };
    let sequence = 0;
    const service = new SessionBriefService({
      repository: new SessionBriefRepository(
        database.connection,
        () => `job-${++sequence}`,
      ),
      observer,
      analyzer,
      clock: () => new Date("2026-07-29T12:00:00.000Z"),
      retentionIntervalMs: 100_000,
      debounceMs: 0,
    });
    service.start();
    await settle();
    const revised = thread("thread-one", "2026-07-29T11:00:00.000Z");
    repository.upsertThread(revised);
    observer.update(snapshot([revised]));
    resolveAnalysis?.(realResult);
    await settle();
    expect(service.snapshot().items[0]).toMatchObject({
      targetUpdatedAt: revised.updatedAt,
      freshness: "current",
      lastGood: { sourceUpdatedAt: revised.updatedAt },
    });
    await service.pauseAndDrain();
    await service.stop();
  });

  it("debounces automatic churn for thirty seconds and coalesces repeated snapshots", async () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-07-29T12:00:00.000Z"));
    database = openDatabase({ path: ":memory:" });
    const observed = thread("thread-one", "2026-07-29T10:00:00.000Z");
    new ObserverRepository(database.connection).upsertThread(observed);
    const observer = new FakeObserver(snapshot([observed]));
    const analyzer: SessionBriefAnalyzer = { analyze: vi.fn(async () => realResult) };
    const service = new SessionBriefService({
      repository: new SessionBriefRepository(database.connection),
      observer,
      analyzer,
      clock: () => new Date(Date.now()),
      retentionIntervalMs: 100_000,
    });
    service.start();
    observer.update(snapshot([observed]));
    await vi.advanceTimersByTimeAsync(29_999);
    expect(analyzer.analyze).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(1);
    await flushPromises();
    expect(analyzer.analyze).toHaveBeenCalledTimes(1);
    expect(service.snapshot().ready).toBe(1);
    await service.stop();
  });

  it("runs exactly two workers and lets a third proceed when a slot is released", async () => {
    database = openDatabase({ path: ":memory:" });
    const threads = ["one", "two", "three"].map((id, index) =>
      thread(`thread-${id}`, `2026-07-29T1${index}:00:00.000Z`)
    );
    const observedRepository = new ObserverRepository(database.connection);
    threads.forEach((value) => observedRepository.upsertThread(value));
    const observer = new FakeObserver(snapshot(threads));
    let active = 0;
    let maximumActive = 0;
    const releases: Array<() => void> = [];
    const analyzer: SessionBriefAnalyzer = {
      analyze: () => new Promise((resolve) => {
        active += 1;
        maximumActive = Math.max(maximumActive, active);
        releases.push(() => {
          active -= 1;
          resolve(realResult);
        });
      }),
    };
    const service = new SessionBriefService({
      repository: new SessionBriefRepository(database.connection),
      observer,
      analyzer,
      debounceMs: 30_000,
      retentionIntervalMs: 100_000,
    });
    service.start();
    service.refreshAll();
    await flushPromises();
    expect(active).toBe(2);
    expect(maximumActive).toBe(2);
    expect(releases).toHaveLength(2);
    releases.shift()?.();
    await flushPromises();
    expect(releases).toHaveLength(2);
    expect(active).toBe(2);
    releases.splice(0).forEach((release) => release());
    await flushPromises();
    expect(maximumActive).toBe(2);
    expect(service.snapshot().ready).toBe(3);
    await service.stop();
  });

  it("retries transient failures after thirty and one-hundred-twenty seconds only", async () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-07-29T12:00:00.000Z"));
    database = openDatabase({ path: ":memory:" });
    const observed = thread("thread-one", "2026-07-29T10:00:00.000Z");
    new ObserverRepository(database.connection).upsertThread(observed);
    const observer = new FakeObserver(snapshot([observed]));
    let attempts = 0;
    const analyzer: SessionBriefAnalyzer = {
      analyze: async () => {
        attempts += 1;
        if (attempts < 3) {
          throw new SessionBriefAnalysisError("timeout", true);
        }
        return realResult;
      },
    };
    const service = new SessionBriefService({
      repository: new SessionBriefRepository(database.connection),
      observer,
      analyzer,
      clock: () => new Date(Date.now()),
      debounceMs: 0,
      retentionIntervalMs: 100_000,
    });
    service.start();
    await vi.advanceTimersByTimeAsync(0);
    await flushPromises();
    expect(attempts).toBe(1);
    await vi.advanceTimersByTimeAsync(29_999);
    expect(attempts).toBe(1);
    await vi.advanceTimersByTimeAsync(1);
    await flushPromises();
    expect(attempts).toBe(2);
    await vi.advanceTimersByTimeAsync(119_999);
    expect(attempts).toBe(2);
    await vi.advanceTimersByTimeAsync(1);
    await flushPromises();
    expect(attempts).toBe(3);
    expect(service.snapshot()).toMatchObject({ ready: 1, failed: 0 });
    await service.stop();
  });

  it("does not retry terminal output failures and keeps the last good result stale", async () => {
    database = openDatabase({ path: ":memory:" });
    const observed = thread("thread-one", "2026-07-29T10:00:00.000Z");
    new ObserverRepository(database.connection).upsertThread(observed);
    const observer = new FakeObserver(snapshot([observed]));
    let attempts = 0;
    const analyzer: SessionBriefAnalyzer = {
      analyze: async () => {
        attempts += 1;
        if (attempts === 1) return realResult;
        throw new SessionBriefAnalysisError("invalid_output", false);
      },
    };
    const service = new SessionBriefService({
      repository: new SessionBriefRepository(database.connection),
      observer,
      analyzer,
      debounceMs: 0,
      retentionIntervalMs: 100_000,
    });
    service.start();
    await settle();
    service.refresh("thread-one");
    await settle();
    expect(attempts).toBe(2);
    expect(service.snapshot().items[0]).toMatchObject({
      analysisStatus: "failed",
      freshness: "current",
      lastGood: { currentState: realResult.content.currentState },
      failure: { category: "invalid_output" },
    });
    await service.stop();
  });

  it("prevents an aborted pre-delete result from promoting after drain", async () => {
    database = openDatabase({ path: ":memory:" });
    const observed = thread("thread-one", "2026-07-29T10:00:00.000Z");
    new ObserverRepository(database.connection).upsertThread(observed);
    const observer = new FakeObserver(snapshot([observed]));
    const analyzer: SessionBriefAnalyzer = {
      analyze: ({ signal }) => new Promise((resolve) => {
        signal?.addEventListener("abort", () => resolve(realResult), { once: true });
      }),
    };
    const briefRepository = new SessionBriefRepository(database.connection);
    const service = new SessionBriefService({
      repository: briefRepository,
      observer,
      analyzer,
      debounceMs: 0,
      retentionIntervalMs: 100_000,
    });
    service.start();
    await flushPromises();
    expect(service.snapshot().analyzing).toBe(1);
    await service.pauseAndDrain();
    expect(briefRepository.listBriefRowsForExport()).toEqual([]);
    database.connection.prepare("DELETE FROM session_brief_jobs").run();
    expect(briefRepository.listBriefRowsForExport()).toEqual([]);
    await service.stop();
  });
});
