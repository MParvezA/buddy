import { isObject } from "../codex/app-server-protocol.js";

export const MAX_SESSION_BRIEF_INPUT_CODE_POINTS = 32_000;

export interface BoundedSessionBriefInput {
  sourceBlock: string;
  evidenceLabels: string[];
}

interface Segment {
  label: string;
  role: "USER" | "ASSISTANT";
  text: string;
  priority: "intent" | "recent";
  order: number;
}

function cleanText(value: string): string {
  return value
    .replace(/\r\n?/g, "\n")
    // eslint-disable-next-line no-control-regex
    .replace(/[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]/g, "")
    .trim();
}

function userTexts(item: unknown): string[] {
  if (!isObject(item) || item.type !== "userMessage") return [];
  if (!Array.isArray(item.content)) return [];
  return item.content.flatMap((content) =>
    isObject(content) && content.type === "text" && typeof content.text === "string"
      ? [cleanText(content.text)]
      : []
  ).filter(Boolean);
}

function assistantText(item: unknown): string | null {
  if (
    !isObject(item) ||
    item.type !== "agentMessage" ||
    typeof item.text !== "string"
  ) {
    return null;
  }
  return cleanText(item.text) || null;
}

function turnId(turn: unknown, index: number): string {
  return isObject(turn) && typeof turn.id === "string" && turn.id
    ? turn.id
    : `position-${index}`;
}

function render(segment: Segment): string {
  return `[${segment.label}] ${segment.role}\n${segment.text}`;
}

function codePoints(value: string): string[] {
  return Array.from(value);
}

function truncateSegment(segment: Segment, maximum: number): Segment | null {
  const marker = "\n[TRUNCATED]";
  const header = `[${segment.label}] ${segment.role}\n`;
  const room = maximum - codePoints(header + marker).length;
  if (room <= 0) return null;
  const text = codePoints(segment.text);
  if (text.length <= room) return segment;
  return {
    ...segment,
    text: `${text.slice(0, room).join("")}${marker}`,
  };
}

function renderWithinBudget(segments: Segment[], maximum: number): string {
  if (!segments.length || maximum <= 0) return "";
  const separator = "\n\n";
  const full = segments.map(render).join(separator);
  if (codePoints(full).length <= maximum) return full;

  const intent = segments.find((segment) => segment.priority === "intent") ?? null;
  const selected: Segment[] = [];
  let remaining = maximum;
  if (intent) {
    const intentBudget = Math.max(
      1,
      Math.min(codePoints(render(intent)).length, Math.floor(maximum / 3)),
    );
    const boundedIntent = truncateSegment(intent, intentBudget);
    if (boundedIntent) {
      selected.push(boundedIntent);
      remaining -= codePoints(render(boundedIntent)).length;
    }
  }

  const newestFirst = segments
    .filter((segment) => segment !== intent)
    .sort((left, right) => right.order - left.order);
  for (const segment of newestFirst) {
    const separatorCost = selected.length ? codePoints(separator).length : 0;
    const fullCost = codePoints(render(segment)).length;
    if (fullCost + separatorCost <= remaining) {
      selected.push(segment);
      remaining -= fullCost + separatorCost;
      continue;
    }
    const bounded = truncateSegment(segment, remaining - separatorCost);
    if (bounded) selected.push(bounded);
    break;
  }
  return selected.sort((left, right) => left.order - right.order).map(render).join(separator);
}

export function extractSessionBriefInput(
  turnsValue: unknown,
  maximum = MAX_SESSION_BRIEF_INPUT_CODE_POINTS,
): BoundedSessionBriefInput | null {
  if (!Array.isArray(turnsValue) || !Number.isInteger(maximum) || maximum <= 0) {
    return null;
  }
  const turns = turnsValue;
  let firstIntent:
    | { turnId: string; turnIndex: number; text: string }
    | null = null;
  for (let turnIndex = 0; turnIndex < turns.length && !firstIntent; turnIndex += 1) {
    const turn = turns[turnIndex];
    if (!isObject(turn) || !Array.isArray(turn.items)) continue;
    for (const item of turn.items) {
      const text = userTexts(item)[0];
      if (text) {
        firstIntent = { turnId: turnId(turn, turnIndex), turnIndex, text };
        break;
      }
    }
  }
  if (!firstIntent) return null;

  const recentStart = Math.max(0, turns.length - 6);
  const recentTurns = turns.slice(recentStart);
  const segments: Segment[] = [];
  let order = 0;
  if (firstIntent.turnIndex < recentStart) {
    segments.push({
      label: "user:first-intent",
      role: "USER",
      text: firstIntent.text,
      priority: "intent",
      order: order++,
    });
  }
  recentTurns.forEach((turn, recentIndex) => {
    if (!isObject(turn) || !Array.isArray(turn.items)) return;
    const currentTurnId = turnId(turn, recentStart + recentIndex);
    let firstUserInTurn = true;
    for (const item of turn.items) {
      const texts = userTexts(item);
      for (const text of texts) {
        const isIntent =
          firstUserInTurn &&
          currentTurnId === firstIntent?.turnId &&
          text === firstIntent.text;
        segments.push({
          label: isIntent
            ? "user:first-intent"
            : `user:recent-${recentIndex + 1}`,
          role: "USER",
          text,
          priority: isIntent ? "intent" : "recent",
          order: order++,
        });
        firstUserInTurn = false;
      }
      const text = assistantText(item);
      if (text) {
        segments.push({
          label: `assistant:recent-${recentIndex + 1}`,
          role: "ASSISTANT",
          text,
          priority: "recent",
          order: order++,
        });
      }
    }
  });
  const sourceBlock = renderWithinBudget(segments, maximum);
  if (!sourceBlock) return null;
  const survivingLabels = [...sourceBlock.matchAll(/^\[([^\]]+)\] /gm)]
    .map((match) => match[1])
    .filter((label): label is string => Boolean(label));
  return {
    sourceBlock,
    evidenceLabels: [...new Set(survivingLabels)],
  };
}
