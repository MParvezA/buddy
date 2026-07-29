// @vitest-environment node
import { EventEmitter } from "node:events";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  PlaceholderBriefAnalyzer,
  type SessionBriefAnalyzer,
} from "../../../src/server/briefs/placeholder-brief-analyzer.js";
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

  it("waits for observer readiness, emits placeholder results, and refreshes idempotently", async () => {
    database = openDatabase({ path: ":memory:" });
    const observed = thread("thread-one", "2026-07-29T10:00:00.000Z");
    new ObserverRepository(database.connection).upsertThread(observed);
    const observer = new FakeObserver(snapshot([observed], "disconnected"));
    const analyzer = new PlaceholderBriefAnalyzer();
    const analyze = vi.spyOn(analyzer, "analyze");
    const service = new SessionBriefService({
      repository: new SessionBriefRepository(database.connection, () => "job-one"),
      observer,
      analyzer,
      clock: () => new Date("2026-07-29T12:00:00.000Z"),
      retentionIntervalMs: 100_000,
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
    expect(analyze).toHaveBeenCalledWith({
      threadId: "thread-one",
      sourceUpdatedAt: observed.updatedAt,
    });
    expect(service.snapshot().items[0]).toMatchObject({
      analysisStatus: "ready",
      freshness: "current",
      lastGood: {
        generator: "deterministic_placeholder",
        modelId: null,
        done: [],
        operatorActions: [],
        blockers: [],
        evidence: [],
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
    const placeholderResult = {
      content: {
        currentState: "Session metadata is ready for future GPT-5.6 analysis.",
        done: [],
        operatorActions: [],
        blockers: [],
        confidence: "low" as const,
        evidence: [],
      },
      generator: "deterministic_placeholder",
      modelId: null,
    };
    const analyzer: SessionBriefAnalyzer = {
      analyze: () => {
        analysisCount += 1;
        return analysisCount === 1
          ? new Promise((resolve) => {
              resolveAnalysis = resolve;
            })
          : Promise.resolve(placeholderResult);
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
    });
    service.start();
    await settle();
    const revised = thread("thread-one", "2026-07-29T11:00:00.000Z");
    repository.upsertThread(revised);
    observer.update(snapshot([revised]));
    resolveAnalysis?.(placeholderResult);
    await settle();
    expect(service.snapshot().items[0]).toMatchObject({
      targetUpdatedAt: revised.updatedAt,
      freshness: "current",
      lastGood: { sourceUpdatedAt: revised.updatedAt },
    });
    await service.pauseAndDrain();
    await service.stop();
  });
});
