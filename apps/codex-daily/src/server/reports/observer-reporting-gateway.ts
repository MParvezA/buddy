import type { FactualDigest } from "../../shared/report.js";
import { ObserverService } from "../codex/observer-service.js";
import type {
  ReportingThreadGateway,
  StructuredNarrativeOutput,
} from "./reporting-thread.js";

export class ObserverReportingGateway implements ReportingThreadGateway {
  constructor(private readonly observer: ObserverService) {}

  ensureReportingThread(
    existingThreadId: string | null,
    registerReportingThread: (threadId: string) => void,
  ): Promise<string> {
    return this.observer.ensureReportingThread(
      existingThreadId,
      registerReportingThread,
    );
  }

  readFinalAssistantMessage(threadId: string): Promise<string | null> {
    return this.observer.readFinalAssistantMessage(threadId);
  }

  async generateStructuredNarrative(input: {
    reportingThreadId: string;
    factualDigest: FactualDigest;
    linkedFinalMessages: Array<{ threadId: string; finalAssistantMessage: string }>;
  }): Promise<StructuredNarrativeOutput> {
    const prompt = [
      "Create a concise daily interpretation from the frozen factual digest below.",
      "Return JSON only with this exact shape:",
      '{"text":"short narrative","suggestions":[{"taskId":"planned task id","reason":"max 280 chars","sourceThreadIds":["linked thread id"]}]}',
      "Suggestions are advisory and must only reference planned task IDs and their linked thread IDs.",
      "Do not claim a task is confirmed complete unless the factual digest says so.",
      JSON.stringify({
        factualDigest: input.factualDigest,
        linkedFinalAssistantMessages: input.linkedFinalMessages,
      }),
    ].join("\n\n");
    const raw = await this.observer.runReportingTurn(input.reportingThreadId, prompt);
    return parseStructuredNarrative(raw);
  }
}

export function parseStructuredNarrative(raw: string): StructuredNarrativeOutput {
  const trimmed = raw.trim();
  const json = trimmed.startsWith("```")
    ? trimmed.replace(/^```(?:json)?\s*/i, "").replace(/\s*```$/, "")
    : trimmed;
  let value: unknown;
  try {
    value = JSON.parse(json);
  } catch {
    throw new Error("Codex reporting output was not valid JSON.");
  }
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new Error("Codex reporting output was malformed.");
  }
  const record = value as Record<string, unknown>;
  if (typeof record.text !== "string" || !Array.isArray(record.suggestions)) {
    throw new Error("Codex reporting output was malformed.");
  }
  const suggestions = record.suggestions.map((item) => {
    if (!item || typeof item !== "object" || Array.isArray(item)) {
      throw new Error("Codex reporting suggestion was malformed.");
    }
    const suggestion = item as Record<string, unknown>;
    if (
      typeof suggestion.taskId !== "string" ||
      typeof suggestion.reason !== "string" ||
      !Array.isArray(suggestion.sourceThreadIds) ||
      suggestion.sourceThreadIds.some((id) => typeof id !== "string")
    ) {
      throw new Error("Codex reporting suggestion was malformed.");
    }
    return {
      taskId: suggestion.taskId,
      reason: suggestion.reason,
      sourceThreadIds: suggestion.sourceThreadIds as string[],
    };
  });
  return { text: record.text, suggestions };
}
