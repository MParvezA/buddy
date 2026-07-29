// @vitest-environment node
import { describe, expect, it } from "vitest";
import { buildFactualDigest, type FactualDigestInput } from "../../../src/server/reports/factual-digest.js";

const input: FactualDigestInput = {
  localDate: "2026-07-29",
  cutoff: "2026-07-29T16:00:00.000Z",
  tasks: [
    {
      taskId: "pending",
      title: "Pending task",
      clarification: null,
      position: 2,
      lifecycle: "open",
      suggestedComplete: false,
      blocked: false,
      threadIds: [],
    },
    {
      taskId: "done",
      title: "Done task",
      clarification: null,
      position: 0,
      lifecycle: "confirmed_complete",
      suggestedComplete: false,
      blocked: false,
      threadIds: ["thread-done"],
    },
    {
      taskId: "blocked",
      title: "Blocked task",
      clarification: "Waiting locally",
      position: 1,
      lifecycle: "open",
      suggestedComplete: true,
      blocked: true,
      threadIds: ["thread-blocked"],
    },
  ],
  threads: [
    {
      threadId: "unplanned",
      title: "New work",
      activityCount: 2,
      lastActivityAt: "2026-07-29T15:00:00.000Z",
      linked: false,
    },
  ],
  attention: [
    {
      attentionId: "attention",
      threadId: "thread-blocked",
      kind: "explicit_blocker",
      certainty: "explicit",
      label: "Explicit blocker",
      occurredAt: "2026-07-29T14:00:00.000Z",
    },
  ],
};

describe("factual digest", () => {
  it("is deterministic and keeps every certainty category separate", () => {
    const first = buildFactualDigest(input);
    const second = buildFactualDigest({
      ...input,
      tasks: [...input.tasks].reverse(),
    });

    expect(JSON.stringify(first)).toBe(JSON.stringify(second));
    expect(first.planned.map((task) => task.taskId)).toEqual(["done", "blocked", "pending"]);
    expect(first.confirmedComplete.map((task) => task.taskId)).toEqual(["done"]);
    expect(first.suggestedComplete.map((task) => task.taskId)).toEqual(["blocked"]);
    expect(first.blocked.map((task) => task.taskId)).toEqual(["blocked"]);
    expect(first.pending.map((task) => task.taskId)).toEqual(["pending"]);
    expect(first.considerTomorrow.map((item) => item.reason)).toEqual([
      "blocked",
      "pending",
      "unplanned",
    ]);
    expect(JSON.stringify(first)).not.toMatch(/transcript|prompt|response|reasoning/i);
  });
});
