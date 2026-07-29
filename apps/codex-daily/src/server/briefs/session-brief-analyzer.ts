import type {
  SessionBriefContent,
  SessionBriefFailureCategory,
} from "../../shared/session-briefs.js";

export interface SessionBriefAnalysisInput {
  threadId: string;
  sourceUpdatedAt: string;
  signal?: AbortSignal;
}

export interface SessionBriefAnalysisResult {
  content: SessionBriefContent;
  generator: "codex_app_server";
  modelId: "gpt-5.6-sol";
}

export interface SessionBriefAnalyzer {
  analyze(input: SessionBriefAnalysisInput): Promise<SessionBriefAnalysisResult>;
}

export class SessionBriefSourceSupersededError extends Error {
  constructor(readonly sourceUpdatedAt: string) {
    super("Session brief source revision was superseded.");
    this.name = "SessionBriefSourceSupersededError";
  }
}

export class SessionBriefAnalysisError extends Error {
  constructor(
    readonly category: SessionBriefFailureCategory,
    readonly transient: boolean,
  ) {
    super(`Session brief analysis failed (${category}).`);
    this.name = "SessionBriefAnalysisError";
  }
}
