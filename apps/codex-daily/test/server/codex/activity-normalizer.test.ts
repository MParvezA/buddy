// @vitest-environment node
import { describe, expect, it } from "vitest";
import {
  normalizeMessage,
  normalizeThread,
  runtimeProjection,
} from "../../../src/server/codex/activity-normalizer.js";

const now = () => new Date("2026-07-29T12:00:00.000Z");

describe("activity normalization", () => {
  it("normalizes status and structured blocker state without retaining content", () => {
    expect(
      runtimeProjection({
        type: "active",
        activeFlags: ["waitingOnApproval", "waitingOnUserInput"],
      }),
    ).toEqual({
      runtime: "active",
      waitingOnApproval: true,
      waitingOnUserInput: true,
    });

    const normalized = normalizeMessage(
      {
        method: "thread/goal/updated",
        params: {
          threadId: "thread-one",
          turnId: "turn-one",
          goal: {
            status: "blocked",
            objective: "SECRET GOAL",
            updatedAt: 1785320000,
          },
        },
      },
      now,
    );
    expect(normalized.activity).toMatchObject({
      category: "goal",
      lifecycle: "blocked",
      label: "Goal blocked",
    });
    expect(JSON.stringify(normalized)).not.toContain("SECRET");
  });

  it("strips prompts, commands, diffs, reasoning, and item bodies", () => {
    const normalized = normalizeMessage(
      {
        id: 44,
        method: "item/commandExecution/requestApproval",
        params: {
          threadId: "thread-one",
          turnId: "turn-one",
          itemId: "item-one",
          startedAtMs: 1785320000000,
          command: "rm SECRET",
          reason: "SECRET REASON",
          diff: "SECRET DIFF",
        },
      },
      now,
      "connection-1",
    );
    expect(normalized.activity).toMatchObject({
      sourceKey: "request:connection-1:thread-one:44:pending",
      category: "approval",
      lifecycle: "pending",
    });
    expect(JSON.stringify(normalized)).not.toMatch(/rm SECRET|SECRET REASON|SECRET DIFF/);
  });

  it("keeps reused request IDs distinct across connection generations", () => {
    const request = {
      id: 44,
      method: "item/tool/requestUserInput",
      params: {
        threadId: "thread-one",
        turnId: "turn-one",
        itemId: "item-one",
      },
    };
    const first = normalizeMessage(
      request,
      now,
      "process-1:connection-1",
    ).activity;
    const replayedId = normalizeMessage(
      request,
      now,
      "process-2:connection-1",
    ).activity;
    const resolved = normalizeMessage(
      {
        method: "serverRequest/resolved",
        params: { threadId: "thread-one", requestId: 44 },
      },
      now,
      "process-2:connection-1",
    ).activity;

    expect(first?.sourceKey).not.toBe(replayedId?.sourceKey);
    expect(replayedId?.sourceKey).toBe(
      "request:process-2:connection-1:thread-one:44:pending",
    );
    expect(resolved?.sourceKey).toBe(
      "request:process-2:connection-1:thread-one:44:resolved",
    );
  });

  it("excludes child/subagent threads and never uses preview as title", () => {
    const base = {
      id: "thread-one",
      sessionId: "session-one",
      parentThreadId: null,
      preview: "SECRET PREVIEW",
      source: "cli",
      cwd: "/workspace",
      cliVersion: "0.146.0",
      createdAt: 1785312000,
      updatedAt: 1785320000,
      recencyAt: null,
      status: { type: "idle" },
      name: null,
    };
    expect(normalizeThread(base, false, now)?.title).toBeNull();
    expect(normalizeThread({ ...base, parentThreadId: "parent" }, false, now)).toBeNull();
    expect(
      normalizeThread({ ...base, source: { subAgent: "review" } }, false, now),
    ).toBeNull();
  });
});
