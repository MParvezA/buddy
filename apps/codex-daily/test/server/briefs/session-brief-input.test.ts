// @vitest-environment node
import { describe, expect, it } from "vitest";
import {
  extractSessionBriefInput,
  MAX_SESSION_BRIEF_INPUT_CODE_POINTS,
} from "../../../src/server/briefs/session-brief-input.js";

function turn(id: string, items: unknown[]) {
  return { id, status: "completed", items };
}

function user(text: string, extras: Record<string, unknown> = {}) {
  return {
    type: "userMessage",
    content: [{ type: "text", text }],
    ...extras,
  };
}

describe("session brief input extraction", () => {
  it("keeps first intent and final six turns, deduplicates overlap, and drops unsupported data", () => {
    const turns = [
      turn("old-intent", [
        user("first intent", { password: "STRUCTURED_SECRET" }),
        { type: "reasoning", summary: "REASONING_SECRET" },
        { type: "commandExecution", command: "COMMAND_SECRET" },
      ]),
      turn("old-two", [{ type: "agentMessage", text: "old assistant omitted" }]),
      ...Array.from({ length: 6 }, (_, index) =>
        turn(`recent-${index + 1}`, [
          user(`recent user ${index + 1}`),
          { type: "agentMessage", text: `recent assistant ${index + 1}` },
          { type: "fileChange", changes: "DIFF_SECRET" },
        ])
      ),
    ];
    const result = extractSessionBriefInput(turns)!;
    expect(result.sourceBlock).toContain("[user:first-intent] USER\nfirst intent");
    expect(result.sourceBlock).not.toContain("old assistant omitted");
    expect(result.sourceBlock).toContain("[user:recent-1] USER\nrecent user 1");
    expect(result.sourceBlock).toContain(
      "[assistant:recent-6] ASSISTANT\nrecent assistant 6",
    );
    expect(result.sourceBlock).not.toMatch(
      /STRUCTURED_SECRET|REASONING_SECRET|COMMAND_SECRET|DIFF_SECRET/,
    );
    expect(result.evidenceLabels).toEqual(
      expect.arrayContaining([
        "user:first-intent",
        "user:recent-1",
        "assistant:recent-6",
      ]),
    );
  });

  it("renders an overlapping first-intent turn once", () => {
    const result = extractSessionBriefInput([
      turn("one", [
        user("intent"),
        { type: "agentMessage", text: "answer" },
      ]),
    ])!;
    expect(result.sourceBlock.match(/intent/g)).toHaveLength(2);
    expect(result.sourceBlock.match(/\[user:first-intent\]/g)).toHaveLength(1);
    expect(result.sourceBlock).not.toContain("[user:recent-1] USER\nintent");
  });

  it("counts Unicode code points and keeps deterministic newest-first truncation within cap", () => {
    const result = extractSessionBriefInput(
      [
        turn("intent", [user("start " + "😀".repeat(100))]),
        ...Array.from({ length: 6 }, (_, index) =>
          turn(`recent-${index}`, [
            user(`turn-${index} ` + "😀".repeat(100)),
          ])
        ),
      ],
      220,
    )!;
    expect(Array.from(result.sourceBlock).length).toBeLessThanOrEqual(220);
    expect(result.sourceBlock).toContain("[TRUNCATED]");
    expect(result.sourceBlock).toContain("turn-5");
    expect(result.sourceBlock).not.toContain("turn-0");

    const maximum = extractSessionBriefInput(
      [turn("one", [user("😀".repeat(MAX_SESSION_BRIEF_INPUT_CODE_POINTS))])],
    )!;
    expect(Array.from(maximum.sourceBlock).length)
      .toBeLessThanOrEqual(MAX_SESSION_BRIEF_INPUT_CODE_POINTS);
  });

  it("fails closed for unsupported-only and malformed input", () => {
    expect(
      extractSessionBriefInput([
        turn("one", [{ type: "reasoning", text: "not user text" }]),
      ]),
    ).toBeNull();
    expect(extractSessionBriefInput({ turns: [] })).toBeNull();
  });
});
