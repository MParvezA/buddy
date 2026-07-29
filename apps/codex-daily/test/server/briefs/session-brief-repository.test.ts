// @vitest-environment node
import { afterEach, describe, expect, it } from "vitest";
import { SessionBriefRepository } from "../../../src/server/briefs/session-brief-repository.js";
import {
  openDatabase,
  type PlanningDatabase,
} from "../../../src/server/storage/database.js";
import { ObserverRepository } from "../../../src/server/storage/observer-repository.js";
import type { ObservedThread } from "../../../src/shared/observer-types.js";

let database: PlanningDatabase | undefined;

afterEach(() => {
  database?.close();
  database = undefined;
});

function thread(id = "thread-one", updatedAt = "2026-07-29T10:00:00.000Z"): ObservedThread {
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
    archived: false,
    lastObservedAt: updatedAt,
    runtime: "idle",
    waitingOnApproval: false,
    waitingOnUserInput: false,
    lastActivityAt: null,
  };
}

function setup() {
  database = openDatabase({ path: ":memory:" });
  const observer = new ObserverRepository(database.connection);
  observer.upsertThread(thread());
  let sequence = 0;
  const repository = new SessionBriefRepository(
    database.connection,
    () => `job-${++sequence}`,
  );
  return { observer, repository, db: database.connection };
}

const result = {
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

describe("session brief repository", () => {
  it("keeps last-good content separate and guards promotion by token and revision", () => {
    const { repository } = setup();
    const first = repository.enqueue(
      "thread-one",
      "2026-07-29T10:00:00.000Z",
      "automatic",
      "2026-07-29T10:01:00.000Z",
    )!;
    expect(
      repository.enqueue(
        "thread-one",
        first.targetUpdatedAt,
        "manual",
        "2026-07-29T10:02:00.000Z",
        true,
      )?.jobId,
    ).toBe(first.jobId);
    repository.markAnalyzing(first.jobId, "2026-07-29T10:03:00.000Z");
    expect(
      repository.promote(
        "obsolete",
        "thread-one",
        first.targetUpdatedAt,
        result,
        "2026-07-29T10:04:00.000Z",
      ),
    ).toBe(false);
    expect(
      repository.promote(
        first.jobId,
        "thread-one",
        first.targetUpdatedAt,
        result,
        "2026-07-29T10:04:00.000Z",
      ),
    ).toBe(true);
    expect(
      repository.item("thread-one", first.targetUpdatedAt, first.targetUpdatedAt),
    ).toMatchObject({
      analysisStatus: "ready",
      freshness: "current",
      lastGood: {
        generator: "deterministic_placeholder",
        modelId: null,
        done: [],
      },
    });

    const refresh = repository.enqueue(
      "thread-one",
      first.targetUpdatedAt,
      "manual",
      "2026-07-29T10:05:00.000Z",
      true,
    )!;
    expect(refresh.jobId).not.toBe(first.jobId);
    expect(
      repository.item("thread-one", first.targetUpdatedAt, first.targetUpdatedAt),
    ).toMatchObject({ analysisStatus: "queued", freshness: "current" });
  });

  it("recovers work, preserves a stable grace marker, prunes, and cascades", () => {
    const { repository, observer, db } = setup();
    const job = repository.enqueue(
      "thread-one",
      "2026-07-29T10:00:00.000Z",
      "automatic",
      "2026-07-29T10:01:00.000Z",
    )!;
    repository.markAnalyzing(job.jobId, "2026-07-29T10:02:00.000Z");
    expect(repository.recoverAnalyzing("2026-07-29T10:03:00.000Z")).toBe(1);
    expect(repository.findJob("thread-one")).toMatchObject({
      status: "queued",
      startedAt: null,
      attemptCount: 1,
    });
    repository.markAnalyzing(job.jobId, "2026-07-29T10:04:00.000Z");
    repository.promote(
      job.jobId,
      "thread-one",
      job.targetUpdatedAt,
      result,
      "2026-07-29T10:05:00.000Z",
    );
    repository.reconcileWindow([], "2026-07-29T11:00:00.000Z", "2026-07-28T11:00:00.000Z");
    repository.reconcileWindow([], "2026-07-29T12:00:00.000Z", "2026-07-28T12:00:00.000Z");
    expect(repository.listBriefRowsForExport()[0]?.outOfWindowAt).toBe(
      "2026-07-29T11:00:00.000Z",
    );
    expect(repository.prune("2026-07-30T11:00:00.000Z")).toBe(1);

    observer.upsertThread(thread("thread-two"));
    repository.enqueue(
      "thread-two",
      "2026-07-29T10:00:00.000Z",
      "automatic",
      "2026-07-29T10:00:00.000Z",
    );
    db.prepare("DELETE FROM observed_threads WHERE id = ?").run("thread-two");
    expect(repository.findJob("thread-two")).toBeNull();
    expect(
      db.prepare("PRAGMA foreign_key_check").all(),
    ).toEqual([]);
  });
});
