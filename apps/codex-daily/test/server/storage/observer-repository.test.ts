// @vitest-environment node
import { describe, expect, it } from "vitest";
import { normalizeMessage } from "../../../src/server/codex/activity-normalizer.js";
import { openDatabase } from "../../../src/server/storage/database.js";
import { ObserverRepository } from "../../../src/server/storage/observer-repository.js";
import { PlanningRepository } from "../../../src/server/storage/planning-repository.js";
import type { ObservedThread } from "../../../src/shared/observer-types.js";

const now = "2026-07-29T12:00:00.000Z";
const thread: ObservedThread = {
  id: "thread-one",
  sessionId: "session-one",
  title: "Safe title",
  cwd: "/workspace",
  source: "cli",
  cliVersion: "0.146.0",
  createdAt: now,
  updatedAt: now,
  recencyAt: now,
  archived: false,
  lastObservedAt: now,
  runtime: "idle",
  waitingOnApproval: false,
  waitingOnUserInput: false,
  lastActivityAt: null,
};

describe("ObserverRepository", () => {
  it("deduplicates facts, supports many-to-many links, and deletes no tasks", () => {
    const database = openDatabase({ path: ":memory:" });
    const observer = new ObserverRepository(database.connection);
    const planning = new PlanningRepository(database.connection);
    const first = planning.createTask({
      localDate: "2026-07-29",
      title: "First",
      clarification: null,
      position: 0,
      now,
    });
    const second = planning.createTask({
      localDate: "2026-07-29",
      title: "Second",
      clarification: null,
      position: 1,
      now,
    });
    observer.upsertThread(thread);
    const fact = {
      sourceKey: "turn:one:completed",
      threadId: thread.id,
      turnId: "turn-one",
      itemId: null,
      occurredAt: now,
      category: "turn" as const,
      lifecycle: "completed",
      label: "Turn completed",
    };
    expect(observer.addActivity(fact)).toBe(true);
    expect(observer.addActivity(fact)).toBe(false);
    expect(observer.link(first.id, thread.id, now)).toBe("linked");
    expect(observer.link(first.id, thread.id, now)).toBe("linked");
    expect(observer.link(second.id, thread.id, now)).toBe("linked");
    expect(observer.listLinks()).toHaveLength(2);
    expect(observer.unlink(first.id, thread.id)).toBe("unlinked");
    expect(planning.findTask(first.id)?.lifecycle).toBe("open");
    database.close();
  });

  it("filters a reporting thread and removes its retained observer facts", () => {
    const database = openDatabase({ path: ":memory:" });
    const observer = new ObserverRepository(database.connection);
    observer.upsertThread(thread);
    observer.exclude(thread.id, now);
    expect(observer.findThread(thread.id)).toBeNull();
    expect(observer.upsertThread(thread)).toBe(false);
    expect(observer.listThreads()).toEqual([]);

    const columns = database.connection
      .prepare("PRAGMA table_info(observed_activities)")
      .all()
      .map((row) => (row as { name: string }).name);
    expect(columns).not.toEqual(
      expect.arrayContaining(["preview", "message", "prompt", "response", "command", "diff", "raw_json"]),
    );
    database.close();
  });

  it("keeps reused server request IDs distinct and resolves them within each thread", () => {
    const database = openDatabase({ path: ":memory:" });
    const observer = new ObserverRepository(database.connection);
    observer.upsertThread(thread);
    observer.upsertThread({
      ...thread,
      id: "thread-two",
      sessionId: "session-two",
      title: "Second safe title",
    });
    const clock = () => new Date(now);

    for (const threadId of ["thread-one", "thread-two"]) {
      const pending = normalizeMessage(
        {
          id: 7,
          method: "item/tool/requestUserInput",
          params: {
            threadId,
            turnId: "turn-one",
            itemId: "item-one",
            questions: [{ id: "secret-question", question: "SECRET" }],
          },
        },
        clock,
      ).activity!;
      const resolved = normalizeMessage(
        {
          method: "serverRequest/resolved",
          params: { threadId, requestId: 7 },
        },
        clock,
      ).activity!;
      expect(observer.addActivity(pending)).toBe(true);
      expect(observer.addActivity(resolved)).toBe(true);
    }

    const activities = observer.listActivities();
    expect(activities.map((activity) => activity.sourceKey).sort()).toEqual([
      "request:thread-one:7:pending",
      "request:thread-one:7:resolved",
      "request:thread-two:7:pending",
      "request:thread-two:7:resolved",
    ]);
    expect(
      activities.filter((activity) => activity.threadId === "thread-one"),
    ).toHaveLength(2);
    expect(
      activities.filter((activity) => activity.threadId === "thread-two"),
    ).toHaveLength(2);
    expect(JSON.stringify(activities)).not.toContain("SECRET");
    database.close();
  });

  it("retains repeated goal-clear episodes after new blocked episodes", () => {
    const database = openDatabase({ path: ":memory:" });
    const observer = new ObserverRepository(database.connection);
    observer.upsertThread(thread);
    const times = [
      "2026-07-29T12:00:01.000Z",
      "2026-07-29T12:00:02.000Z",
      "2026-07-29T12:00:03.000Z",
      "2026-07-29T12:00:04.000Z",
    ];
    let index = 0;
    const clock = () => new Date(times[index++]);
    const episodes = [
      {
        method: "thread/goal/updated",
        params: {
          threadId: thread.id,
          turnId: "turn-one",
          goal: { status: "blocked", updatedAt: 1785320001, objective: "SECRET ONE" },
        },
      },
      { method: "thread/goal/cleared", params: { threadId: thread.id } },
      {
        method: "thread/goal/updated",
        params: {
          threadId: thread.id,
          turnId: "turn-two",
          goal: { status: "blocked", updatedAt: 1785320003, objective: "SECRET TWO" },
        },
      },
      { method: "thread/goal/cleared", params: { threadId: thread.id } },
    ];

    for (const envelope of episodes) {
      const normalized = normalizeMessage(envelope, clock).activity!;
      expect(observer.addActivity(normalized)).toBe(true);
    }

    const activities = observer
      .listActivities()
      .filter((activity) => activity.category === "goal");
    expect(activities).toHaveLength(4);
    expect(activities.filter((activity) => activity.lifecycle === "blocked")).toHaveLength(2);
    expect(activities.filter((activity) => activity.lifecycle === "cleared")).toHaveLength(2);
    expect(new Set(activities.map((activity) => activity.sourceKey)).size).toBe(4);
    expect(JSON.stringify(activities)).not.toContain("SECRET");
    database.close();
  });
});
