// @vitest-environment node
import { describe, expect, it } from "vitest";
import { AttentionRepository } from "../../../src/server/attention/attention-repository.js";
import { openDatabase } from "../../../src/server/storage/database.js";
import { ObserverRepository } from "../../../src/server/storage/observer-repository.js";
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
  runtime: "active",
  waitingOnApproval: false,
  waitingOnUserInput: false,
  lastActivityAt: now,
};

describe("AttentionRepository", () => {
  it("persists normalized metadata, deduplicates, and keeps local actions local", () => {
    const database = openDatabase({ path: ":memory:" });
    new ObserverRepository(database.connection).upsertThread(thread);
    const repository = new AttentionRepository(database.connection);
    const candidate = {
      sourceKey: "request:thread-one:7:pending",
      threadId: thread.id,
      turnId: "turn-one",
      itemId: "item-one",
      kind: "approval" as const,
      certainty: "explicit" as const,
      sourceOccurredAt: now,
      sourceLabel: "Command approval requested",
    };
    repository.upsert(candidate, now);
    repository.upsert(candidate, now);
    expect(repository.listOpen()).toHaveLength(1);
    const item = repository.listOpen()[0];
    expect(repository.markLocal(item.id, "acknowledged", now)).toBe("updated");
    expect(repository.listOpen()).toEqual([]);
    expect(repository.find(item.id)).toMatchObject({
      lifecycle: "acknowledged",
      localActionAt: now,
    });
    expect(repository.markLocal(item.id, "dismissed", now)).toBe("not_actionable");
    expect(repository.find(item.id)?.lifecycle).toBe("acknowledged");

    const columns = database.connection
      .prepare("PRAGMA table_info(attention_items)")
      .all()
      .map((row) => (row as { name: string }).name);
    expect(columns).not.toEqual(
      expect.arrayContaining([
        "request_body",
        "question",
        "prompt",
        "answer",
        "transcript",
        "raw_json",
      ]),
    );
    expect(JSON.stringify(repository.listForThread(thread.id))).not.toMatch(
      /SECRET|prompt|answer|transcript/i,
    );
    database.close();
  });
});
