import type { FactualDigest } from "../../shared/report.js";
import type {
  NarrativeResult,
  ReportNarrativeProvider,
} from "./report-service.js";

export interface StructuredNarrativeOutput {
  text: string;
  suggestions: NarrativeResult["suggestions"];
}

export interface ReportingThreadGateway {
  ensureReportingThread(
    existingThreadId: string | null,
    registerReportingThread: (threadId: string) => void,
  ): Promise<string>;
  readFinalAssistantMessage(threadId: string): Promise<string | null>;
  generateStructuredNarrative(input: {
    reportingThreadId: string;
    factualDigest: FactualDigest;
    linkedFinalMessages: Array<{ threadId: string; finalAssistantMessage: string }>;
  }): Promise<StructuredNarrativeOutput>;
}

export class ReportingThreadNarrativeProvider implements ReportNarrativeProvider {
  constructor(
    private readonly gateway: ReportingThreadGateway,
    private readonly maximumMessageCharacters = 2_000,
    private readonly maximumContextCharacters = 12_000,
  ) {}

  async generate(input: {
    snapshotId: string;
    digest: FactualDigest;
    existingReportingThreadId: string | null;
    registerReportingThread: (threadId: string) => void;
  }): Promise<NarrativeResult> {
    const reportingThreadId = await this.gateway.ensureReportingThread(
      input.existingReportingThreadId,
      input.registerReportingThread,
    );
    const threadIds = [
      ...new Set(input.digest.planned.flatMap((task) => task.threadIds)),
    ].sort();
    const linkedFinalMessages: Array<{
      threadId: string;
      finalAssistantMessage: string;
    }> = [];
    let retained = 0;
    for (const threadId of threadIds) {
      const raw = await this.gateway.readFinalAssistantMessage(threadId);
      if (!raw) continue;
      const remaining = this.maximumContextCharacters - retained;
      if (remaining <= 0) break;
      const finalAssistantMessage = raw
        .slice(0, Math.min(this.maximumMessageCharacters, remaining))
        .trim();
      if (!finalAssistantMessage) continue;
      retained += finalAssistantMessage.length;
      linkedFinalMessages.push({ threadId, finalAssistantMessage });
    }
    const output = await this.gateway.generateStructuredNarrative({
      reportingThreadId,
      factualDigest: input.digest,
      linkedFinalMessages,
    });
    // Message bodies remain request-local and are discarded when this call ends.
    return {
      reportingThreadId,
      text: output.text,
      suggestions: output.suggestions,
    };
  }
}
