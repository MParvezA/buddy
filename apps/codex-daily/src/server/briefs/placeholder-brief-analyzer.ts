import type { SessionBriefContent } from "../../shared/session-briefs.js";
import { PLACEHOLDER_CURRENT_STATE } from "./session-brief-validator.js";

export interface SessionBriefAnalysisInput {
  threadId: string;
  sourceUpdatedAt: string;
}

export interface SessionBriefAnalysisResult {
  content: SessionBriefContent;
  generator: string;
  modelId: string | null;
}

export interface SessionBriefAnalyzer {
  analyze(input: SessionBriefAnalysisInput): Promise<SessionBriefAnalysisResult>;
}

export class PlaceholderBriefAnalyzer implements SessionBriefAnalyzer {
  async analyze(
    input: SessionBriefAnalysisInput,
  ): Promise<SessionBriefAnalysisResult> {
    void input;
    return {
      content: {
        currentState: PLACEHOLDER_CURRENT_STATE,
        done: [],
        operatorActions: [],
        blockers: [],
        confidence: "low",
        evidence: [],
      },
      generator: "deterministic_placeholder",
      modelId: null,
    };
  }
}
