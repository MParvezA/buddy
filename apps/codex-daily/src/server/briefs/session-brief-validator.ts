import type {
  SessionBriefConfidence,
  SessionBriefContent,
  SessionBriefLastGood,
} from "../../shared/session-briefs.js";

// eslint-disable-next-line no-control-regex
const CONTROL_CHARACTERS = /[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]/;
const HTML_MARKUP = /<\/?[A-Za-z][^>]*>/;
const CREDENTIAL_URL = /\b[a-z][a-z0-9+.-]*:\/\/[^/\s:@]+:[^/\s@]+@/i;
const EVIDENCE = /^(user|assistant):(first-intent|recent-[1-6])$/;
const CONFIDENCE = new Set<SessionBriefConfidence>(["high", "medium", "low"]);
function isExactObject(
  value: unknown,
  keys: readonly string[],
): value is Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const actual = Object.keys(value).sort();
  return actual.length === keys.length &&
    keys.slice().sort().every((key, index) => key === actual[index]);
}

function safeText(value: unknown, maximum: number, name: string): string {
  if (typeof value !== "string") throw new Error(`${name} must be text.`);
  const text = value.trim();
  if (!text || Array.from(text).length > maximum) {
    throw new Error(`${name} has an invalid length.`);
  }
  if (
    CONTROL_CHARACTERS.test(text) ||
    HTML_MARKUP.test(text) ||
    CREDENTIAL_URL.test(text)
  ) {
    throw new Error(`${name} contains unsafe content.`);
  }
  return text;
}

function safeList(
  value: unknown,
  maximumItems: number,
  maximumCharacters: number,
  name: string,
  grammar?: RegExp,
): string[] {
  if (!Array.isArray(value) || value.length > maximumItems) {
    throw new Error(`${name} has an invalid item count.`);
  }
  const result = value.map((item, index) => {
    const text = safeText(item, maximumCharacters, `${name}[${index}]`);
    if (grammar && !grammar.test(text)) {
      throw new Error(`${name}[${index}] has an invalid format.`);
    }
    return text;
  });
  if (new Set(result).size !== result.length) {
    throw new Error(`${name} contains duplicate items.`);
  }
  return result;
}

export function assertSessionBriefContent(value: unknown): SessionBriefContent {
  const keys = [
    "blockers",
    "confidence",
    "currentState",
    "done",
    "evidence",
    "operatorActions",
  ];
  if (!isExactObject(value, keys)) {
    throw new Error("Session brief content must contain the exact expected fields.");
  }
  if (
    typeof value.confidence !== "string" ||
    !CONFIDENCE.has(value.confidence as SessionBriefConfidence)
  ) {
    throw new Error("Session brief confidence is invalid.");
  }
  return {
    currentState: safeText(value.currentState, 600, "currentState"),
    done: safeList(value.done, 5, 280, "done"),
    operatorActions: safeList(
      value.operatorActions,
      5,
      280,
      "operatorActions",
    ),
    blockers: safeList(value.blockers, 5, 280, "blockers"),
    confidence: value.confidence as SessionBriefConfidence,
    evidence: safeList(value.evidence, 6, 120, "evidence", EVIDENCE),
  };
}

export function assertSessionBriefLastGood(
  value: unknown,
): SessionBriefLastGood {
  const keys = [
    "blockers",
    "confidence",
    "currentState",
    "done",
    "evidence",
    "generatedAt",
    "generator",
    "modelId",
    "operatorActions",
    "sourceUpdatedAt",
  ];
  if (!isExactObject(value, keys)) {
    throw new Error("Stored session brief must contain the exact expected fields.");
  }
  if (value.modelId !== null && typeof value.modelId !== "string") {
    throw new Error("Session brief model ID is invalid.");
  }
  const content = assertSessionBriefContent({
    currentState: value.currentState,
    done: value.done,
    operatorActions: value.operatorActions,
    blockers: value.blockers,
    confidence: value.confidence,
    evidence: value.evidence,
  });
  const stored: SessionBriefLastGood = {
    ...content,
    sourceUpdatedAt: safeText(value.sourceUpdatedAt, 100, "sourceUpdatedAt"),
    generatedAt: safeText(value.generatedAt, 100, "generatedAt"),
    generator: safeText(value.generator, 100, "generator"),
    modelId:
      value.modelId === null ? null : safeText(value.modelId, 100, "modelId"),
  };
  if (
    stored.generator !== "codex_app_server" ||
    stored.modelId !== "gpt-5.6-sol"
  ) {
    throw new Error("Session brief provenance is invalid.");
  }
  return stored;
}
