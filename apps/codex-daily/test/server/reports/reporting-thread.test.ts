// @vitest-environment node
import { describe, expect, it, vi } from "vitest";
import type { FactualDigest } from "../../../src/shared/report.js";
import { ReportingThreadNarrativeProvider } from "../../../src/server/reports/reporting-thread.js";

const digest: FactualDigest = {
  localDate: "2026-07-29",
  cutoff: "2026-07-29T16:00:00.000Z",
  planned: [
    {
      taskId: "task",
      title: "Outcome",
      clarification: null,
      threadIds: ["ordinary"],
    },
  ],
  confirmedComplete: [],
  suggestedComplete: [],
  pending: [],
  blocked: [],
  unplannedWork: [],
  outstandingAttention: [],
  considerTomorrow: [],
};

describe("reporting thread provider", () => {
  it("registers the dedicated thread before transient reads and bounds message context", async () => {
    const calls: string[] = [];
    const gateway = {
      ensureReportingThread: vi.fn(async (
        _existing: string | null,
        register: (threadId: string) => void,
      ) => {
        calls.push("ensure");
        register("reporter");
        return "reporter";
      }),
      readFinalAssistantMessage: vi.fn(async () => {
        calls.push("read");
        return "sensitive transient final message".repeat(200);
      }),
      generateStructuredNarrative: vi.fn(async (input: {
        linkedFinalMessages: Array<{ finalAssistantMessage: string }>;
      }) => {
        calls.push("generate");
        expect(input.linkedFinalMessages[0].finalAssistantMessage.length).toBeLessThanOrEqual(2_000);
        return {
          text: "Generated summary",
          suggestions: [{ taskId: "task", reason: "Looks complete", sourceThreadIds: ["ordinary"] }],
        };
      }),
    };
    const provider = new ReportingThreadNarrativeProvider(gateway);
    const result = await provider.generate({
      snapshotId: "snapshot",
      digest,
      existingReportingThreadId: null,
      registerReportingThread: (id) => calls.push(`register:${id}`),
    });
    expect(calls).toEqual(["ensure", "register:reporter", "read", "generate"]);
    expect(result.text).toBe("Generated summary");
    expect(JSON.stringify(digest)).not.toContain("sensitive transient");
  });
});
