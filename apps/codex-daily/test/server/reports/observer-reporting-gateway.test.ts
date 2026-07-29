// @vitest-environment node
import { describe, expect, it } from "vitest";
import { parseStructuredNarrative } from "../../../src/server/reports/observer-reporting-gateway.js";

describe("observer reporting gateway", () => {
  it("accepts bounded structured JSON and rejects prose or malformed suggestions", () => {
    expect(
      parseStructuredNarrative(
        '```json\n{"text":"Summary","suggestions":[{"taskId":"task","reason":"Done","sourceThreadIds":["thread"]}]}\n```',
      ),
    ).toEqual({
      text: "Summary",
      suggestions: [
        { taskId: "task", reason: "Done", sourceThreadIds: ["thread"] },
      ],
    });
    expect(() => parseStructuredNarrative("A prose answer")).toThrow(/valid JSON/);
    expect(() =>
      parseStructuredNarrative('{"text":"Summary","suggestions":[{"taskId":3}]}'),
    ).toThrow(/malformed/);
  });
});
