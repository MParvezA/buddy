// @vitest-environment node
import { afterEach, describe, expect, it } from "vitest";
import { AttentionEngine } from "../../../src/server/attention/attention-engine.js";
import { AttentionRepository } from "../../../src/server/attention/attention-repository.js";
import {
  openDatabase,
  type PlanningDatabase,
} from "../../../src/server/storage/database.js";
import { ObserverRepository } from "../../../src/server/storage/observer-repository.js";
import type {
  ObservedActivity,
  ObservedThread,
  ObserverSnapshot,
} from "../../../src/shared/observer-types.js";

const baseTime = "2026-07-29T12:00:00.000Z";
const thread: ObservedThread = {
  id: "thread-one",
  sessionId: "session-one",
  title: "Observed chat",
  cwd: "/workspace",
  source: "cli",
  cliVersion: "0.146.0",
  createdAt: baseTime,
  updatedAt: baseTime,
  recencyAt: baseTime,
  archived: false,
  lastObservedAt: baseTime,
  runtime: "active",
  waitingOnApproval: false,
  waitingOnUserInput: false,
  lastActivityAt: baseTime,
};

let database: PlanningDatabase | undefined;

afterEach(() => {
  database?.close();
  database = undefined;
});

function setup(now: string) {
  database = openDatabase({ path: ":memory:" });
  const observer = new ObserverRepository(database.connection);
  observer.upsertThread(thread);
  const attention = new AttentionRepository(database.connection);
  return {
    observer,
    attention,
    engine: new AttentionEngine(attention, () => new Date(now)),
  };
}

function activity(
  sourceKey: string,
  category: ObservedActivity["category"],
  lifecycle: string,
  occurredAt = baseTime,
): ObservedActivity {
  return {
    sourceKey,
    threadId: thread.id,
    turnId: category === "turn" ? "turn-one" : null,
    itemId: null,
    occurredAt,
    category,
    lifecycle,
    label: `${category} ${lifecycle}`,
  };
}

function snapshot(
  activities: ObservedActivity[],
  options: {
    capability?: "standalone_history" | "shared_live";
    state?: "connecting" | "connected" | "reconnecting" | "disconnected";
    observedThread?: ObservedThread;
  } = {},
): ObserverSnapshot {
  return {
    health: {
      state: options.state ?? "connected",
      capability: options.capability ?? "shared_live",
      lastSuccessfulSyncAt: baseTime,
      lastInventoryRefreshAt: baseTime,
      diagnostic: null,
    },
    threads: [options.observedThread ?? thread],
    activities,
    taskLinks: [],
  };
}

describe("AttentionEngine", () => {
  it("maps every explicit source and orders explicit items ahead of possible stale", () => {
    const { engine, attention } = setup("2026-07-29T12:30:00.000Z");
    engine.reconcile(
      snapshot([
        activity("request:thread-one:1:pending", "approval", "pending"),
        activity("request:thread-one:2:pending", "input_request", "pending"),
        activity("turn:thread-one:failed:failed", "turn", "failed"),
        activity("turn:thread-one:interrupted:interrupted", "turn", "interrupted"),
        activity("goal:thread-one:blocked", "goal", "blocked"),
        activity("turn:thread-one:completed:completed", "turn", "completed"),
        activity("item:thread-one:item-one:completed", "item", "completed"),
      ]),
    );

    expect(attention.listOpen().map((item) => item.kind)).toEqual([
      "explicit_blocker",
      "approval",
      "direct_question",
      "failed_turn",
      "interrupted_turn",
      "possibly_stale",
    ]);
    expect(attention.listOpen().slice(0, 5).every((item) => item.certainty === "explicit"))
      .toBe(true);
    expect(attention.listOpen().at(-1)).toMatchObject({
      kind: "possibly_stale",
      certainty: "possible",
    });
    expect(attention.listOpen()).toHaveLength(6);
  });

  it("does not fabricate approvals or questions in standalone history mode", () => {
    const { engine, attention } = setup("2026-07-29T12:05:00.000Z");
    engine.reconcile(
      snapshot(
        [
          activity("request:thread-one:1:pending", "approval", "pending"),
          activity("request:thread-one:2:pending", "input_request", "pending"),
        ],
        { capability: "standalone_history" },
      ),
    );
    expect(attention.listOpen()).toEqual([]);
  });

  it("uses an exact 30-minute stale boundary and excludes non-active states", () => {
    const before = setup("2026-07-29T12:29:59.000Z");
    before.engine.reconcile(snapshot([]));
    expect(before.attention.listOpen()).toEqual([]);
    database?.close();
    database = undefined;

    const atBoundary = setup("2026-07-29T12:30:00.000Z");
    atBoundary.engine.reconcile(snapshot([]));
    expect(atBoundary.attention.listOpen()).toHaveLength(1);
    for (const observedThread of [
      { ...thread, runtime: "idle" as const },
      { ...thread, runtime: "unknown" as const },
      { ...thread, runtime: "system_error" as const },
      { ...thread, archived: true },
    ]) {
      atBoundary.engine.reconcile(
        snapshot([], { observedThread }),
      );
      expect(atBoundary.attention.listOpen()).toEqual([]);
    }
  });

  it("deduplicates replay and source-resolves requests, blockers, and stale episodes", () => {
    const { engine, attention } = setup("2026-07-29T12:30:00.000Z");
    const pending = activity(
      "request:thread-one:7:pending",
      "approval",
      "pending",
    );
    const blocked = activity("goal:thread-one:1", "goal", "blocked");
    engine.reconcile(snapshot([pending, blocked]));
    engine.reconcile(snapshot([pending, blocked]));
    expect(attention.listOpen()).toHaveLength(3);

    engine.reconcile(
      snapshot([
        pending,
        blocked,
        activity("request:thread-one:7:resolved", "input_request", "resolved"),
        activity(
          "goal:thread-one:cleared",
          "goal",
          "cleared",
          "2026-07-29T12:31:00.000Z",
        ),
      ], {
        observedThread: {
          ...thread,
          lastActivityAt: "2026-07-29T12:31:00.000Z",
        },
      }),
    );
    expect(attention.listOpen()).toEqual([]);
    expect(attention.listForThread(thread.id)).toHaveLength(3);
    expect(
      attention
        .listForThread(thread.id)
        .every((item) => item.lifecycle === "source_resolved"),
    ).toBe(true);
  });

  it("preserves the last queue and creates no stale signal while disconnected", () => {
    const { engine, attention } = setup("2026-07-29T12:30:00.000Z");
    const failed = activity("turn:thread-one:failed", "turn", "failed");
    engine.reconcile(
      snapshot([failed], {
        observedThread: {
          ...thread,
          lastActivityAt: "2026-07-29T12:29:00.000Z",
        },
      }),
    );
    expect(attention.listOpen().map((item) => item.kind)).toEqual(["failed_turn"]);
    engine.reconcile(
      snapshot(
        [
          failed,
          activity("goal:thread-one:blocked-while-offline", "goal", "blocked"),
        ],
        { state: "disconnected" },
      ),
    );
    expect(attention.listOpen().map((item) => item.kind)).toEqual(["failed_turn"]);
  });

  it("does not resurrect an acknowledged stale episode on replay or repeated sweeps", () => {
    const { engine, attention } = setup("2026-07-29T12:30:00.000Z");
    const staleSnapshot = snapshot([]);
    engine.reconcile(staleSnapshot);
    const stale = attention.listOpen()[0];
    expect(attention.markLocal(stale.id, "acknowledged", baseTime)).toBe("updated");
    engine.reconcile(staleSnapshot);
    engine.reconcile(staleSnapshot);
    expect(attention.listOpen()).toEqual([]);
    expect(attention.find(stale.id)?.lifecycle).toBe("acknowledged");
  });
});
