// @vitest-environment node
import { describe, expect, it } from "vitest";
import {
  parseSessionBriefOutput,
  sessionBriefOutputSchema,
} from "../../../src/server/briefs/session-brief-output.js";

const valid = {
  currentState: "The chat is implementing the monitor.",
  done: ["The design is approved."],
  operatorActions: ["Review the implementation."],
  blockers: [],
  confidence: "high",
  evidence: ["user:first-intent"],
};

describe("session brief structured output", () => {
  it("builds a strict evidence-specific six-field schema", () => {
    expect(sessionBriefOutputSchema(["user:first-intent"])).toMatchObject({
      type: "object",
      additionalProperties: false,
      required: [
        "currentState",
        "done",
        "operatorActions",
        "blockers",
        "confidence",
        "evidence",
      ],
      properties: {
        evidence: {
          maxItems: 6,
          uniqueItems: true,
          items: { enum: ["user:first-intent"] },
        },
      },
    });
  });

  it("parses raw JSON and applies the input evidence allowlist", () => {
    expect(
      parseSessionBriefOutput(JSON.stringify(valid), ["user:first-intent"]),
    ).toEqual(valid);
    expect(() =>
      parseSessionBriefOutput(
        JSON.stringify({ ...valid, evidence: ["assistant:recent-1"] }),
        ["user:first-intent"],
      ),
    ).toThrow("allowlist");
  });

  it.each([
    ["```json\n{}\n```", "invalid JSON"],
    [JSON.stringify({ ...valid, extra: "raw" }), "exact expected fields"],
    [JSON.stringify({ ...valid, done: ["same", "same"] }), "duplicate"],
    [JSON.stringify({ ...valid, currentState: "<b>unsafe</b>" }), "unsafe"],
    [
      JSON.stringify({
        ...valid,
        operatorActions: ["Visit https://user:secret@example.test"],
      }),
      "unsafe",
    ],
  ])("rejects noncanonical output", (raw, message) => {
    expect(() =>
      parseSessionBriefOutput(raw, ["user:first-intent"]),
    ).toThrow(message);
  });
});
