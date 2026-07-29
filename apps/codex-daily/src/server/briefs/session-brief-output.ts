import type { SessionBriefContent } from "../../shared/session-briefs.js";
import { assertSessionBriefContent } from "./session-brief-validator.js";

export function sessionBriefOutputSchema(evidenceLabels: string[]): Record<string, unknown> {
  const text = (maximum: number) => ({
    type: "string",
    minLength: 1,
    maxLength: maximum,
  });
  const list = (maximumItems: number, maximumCharacters: number) => ({
    type: "array",
    maxItems: maximumItems,
    uniqueItems: true,
    items: text(maximumCharacters),
  });
  return {
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
      currentState: text(600),
      done: list(5, 280),
      operatorActions: list(5, 280),
      blockers: list(5, 280),
      confidence: { type: "string", enum: ["high", "medium", "low"] },
      evidence: {
        type: "array",
        maxItems: 6,
        uniqueItems: true,
        items: {
          type: "string",
          maxLength: 120,
          enum: evidenceLabels,
        },
      },
    },
  };
}

export function parseSessionBriefOutput(
  raw: string,
  evidenceLabels: readonly string[],
): SessionBriefContent {
  let value: unknown;
  try {
    value = JSON.parse(raw.trim());
  } catch {
    throw new Error("Session brief output is invalid JSON.");
  }
  const content = assertSessionBriefContent(value);
  const allowlist = new Set(evidenceLabels);
  if (content.evidence.some((label) => !allowlist.has(label))) {
    throw new Error("Session brief evidence is outside the input allowlist.");
  }
  return content;
}
