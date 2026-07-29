// @vitest-environment node
import { describe, expect, it } from "vitest";
import {
  assertSessionBriefContent,
  assertSessionBriefLastGood,
} from "../../../src/server/briefs/session-brief-validator.js";

const valid = {
  currentState: "The chat is preparing an implementation.",
  done: ["The design was approved."],
  operatorActions: ["Review the proposed implementation."],
  blockers: [],
  confidence: "high",
  evidence: ["user:first-intent", "assistant:recent-1"],
};

describe("session brief validation", () => {
  it("trims and accepts only the bounded structured contract", () => {
    expect(
      assertSessionBriefContent({
        ...valid,
        currentState: ` ${valid.currentState} `,
      }),
    ).toEqual(valid);
  });

  it.each([
    [{ ...valid, extra: "raw output" }, "exact expected fields"],
    [{ ...valid, currentState: "x".repeat(601) }, "invalid length"],
    [{ ...valid, done: Array.from({ length: 6 }, () => "done") }, "item count"],
    [{ ...valid, evidence: ["system:recent-1"] }, "invalid format"],
    [{ ...valid, currentState: "<script>secret</script>" }, "unsafe content"],
    [{ ...valid, currentState: "https://user:secret@example.test/work" }, "unsafe content"],
    [{ ...valid, currentState: "unsafe\u0000text" }, "unsafe content"],
    [{ ...valid, confidence: "certain" }, "confidence"],
  ])("rejects malformed or unsafe values", (value, message) => {
    expect(() => assertSessionBriefContent(value)).toThrow(message);
  });

  it("accepts only the canonical GPT-5.6 App Server provenance", () => {
    expect(() =>
      assertSessionBriefLastGood({
        ...valid,
        sourceUpdatedAt: "2026-07-29T10:00:00.000Z",
        generatedAt: "2026-07-29T10:01:00.000Z",
        generator: "deterministic_placeholder",
        modelId: null,
      }),
    ).toThrow("provenance");
    expect(() =>
      assertSessionBriefLastGood({
        currentState:
          "Session metadata is ready for future GPT-5.6 analysis.",
        done: [],
        operatorActions: [],
        blockers: [],
        confidence: "low",
        evidence: [],
        sourceUpdatedAt: "2026-07-29T10:00:00.000Z",
        generatedAt: "2026-07-29T10:01:00.000Z",
        generator: "deterministic_placeholder",
        modelId: "gpt-5.6-sol",
      }),
    ).toThrow("provenance");
    expect(
      assertSessionBriefLastGood({
        ...valid,
        sourceUpdatedAt: "2026-07-29T10:00:00.000Z",
        generatedAt: "2026-07-29T10:01:00.000Z",
        generator: "codex_app_server",
        modelId: "gpt-5.6-sol",
      }),
    ).toMatchObject({
      generator: "codex_app_server",
      modelId: "gpt-5.6-sol",
    });
  });
});
