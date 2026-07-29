import type {
  ObservedActivity,
  ObservedThread,
  ObservedThreadRuntime,
} from "../../shared/observer-types.js";
import {
  isObject,
  objectField,
  optionalString,
  stringField,
  unixMilliseconds,
  unixSeconds,
  type JsonObject,
  type ProtocolMethodEnvelope,
} from "./app-server-protocol.js";

const INTERACTIVE_SOURCES = new Set(["cli", "vscode", "appServer"]);
const KNOWN_ITEM_TYPES = new Set([
  "userMessage",
  "hookPrompt",
  "agentMessage",
  "plan",
  "reasoning",
  "commandExecution",
  "fileChange",
  "mcpToolCall",
  "dynamicToolCall",
  "collabAgentToolCall",
  "subAgentActivity",
  "webSearch",
  "imageView",
  "sleep",
  "imageGeneration",
  "enteredReviewMode",
  "exitedReviewMode",
  "contextCompaction",
]);

export interface RuntimeProjection {
  runtime: ObservedThreadRuntime;
  waitingOnApproval: boolean;
  waitingOnUserInput: boolean;
}

export interface NormalizedMessage {
  thread?: ObservedThread;
  runtime?: { threadId: string } & RuntimeProjection;
  archived?: { threadId: string; value: boolean };
  activity?: ObservedActivity;
  unknown?: boolean;
}

function sourceName(source: unknown): string {
  if (typeof source === "string") return source;
  if (isObject(source) && typeof source.custom === "string") return `custom:${source.custom}`;
  if (isObject(source) && "subAgent" in source) return "subAgent";
  return "unknown";
}

export function runtimeProjection(status: unknown): RuntimeProjection {
  if (!isObject(status) || typeof status.type !== "string") {
    return { runtime: "unknown", waitingOnApproval: false, waitingOnUserInput: false };
  }
  if (status.type === "notLoaded") {
    return { runtime: "not_loaded", waitingOnApproval: false, waitingOnUserInput: false };
  }
  if (status.type === "idle") {
    return { runtime: "idle", waitingOnApproval: false, waitingOnUserInput: false };
  }
  if (status.type === "systemError") {
    return { runtime: "system_error", waitingOnApproval: false, waitingOnUserInput: false };
  }
  if (status.type === "active") {
    const flags = Array.isArray(status.activeFlags) ? status.activeFlags : [];
    return {
      runtime: "active",
      waitingOnApproval: flags.includes("waitingOnApproval"),
      waitingOnUserInput: flags.includes("waitingOnUserInput"),
    };
  }
  return { runtime: "unknown", waitingOnApproval: false, waitingOnUserInput: false };
}

export function normalizeThread(
  value: unknown,
  archived: boolean,
  now: () => Date,
): ObservedThread | null {
  if (!isObject(value)) throw new Error("Codex App Server thread is invalid.");
  const id = stringField(value, "id");
  const sessionId = stringField(value, "sessionId");
  if (value.parentThreadId != null) return null;
  const source = sourceName(value.source);
  if (!INTERACTIVE_SOURCES.has(source)) return null;
  const runtime = runtimeProjection(value.status);
  return {
    id,
    sessionId,
    title: optionalString(value, "name"),
    cwd: stringField(value, "cwd"),
    source,
    cliVersion: stringField(value, "cliVersion"),
    createdAt: unixSeconds(value.createdAt),
    updatedAt: unixSeconds(value.updatedAt),
    recencyAt: value.recencyAt == null ? null : unixSeconds(value.recencyAt),
    archived,
    lastObservedAt: now().toISOString(),
    ...runtime,
    lastActivityAt: null,
  };
}

function activity(input: {
  sourceKey: string;
  threadId: string;
  turnId?: string | null;
  itemId?: string | null;
  occurredAt: string;
  category: ObservedActivity["category"];
  lifecycle: string;
  label: string;
}): ObservedActivity {
  return {
    turnId: null,
    itemId: null,
    ...input,
  };
}

function itemFact(
  envelope: ProtocolMethodEnvelope,
  lifecycle: "started" | "completed",
  now: () => Date,
): ObservedActivity {
  const params = envelope.params;
  const item = objectField(params, "item");
  const threadId = stringField(params, "threadId");
  const turnId = stringField(params, "turnId");
  const itemId = stringField(item, "id");
  const itemType =
    typeof item.type === "string" && KNOWN_ITEM_TYPES.has(item.type) ? item.type : "unknown";
  const timestamp = lifecycle === "started" ? "startedAtMs" : "completedAtMs";
  return activity({
    sourceKey: `item:${threadId}:${turnId}:${itemId}:${lifecycle}`,
    threadId,
    turnId,
    itemId,
    occurredAt: unixMilliseconds(isObject(params) ? params[timestamp] : null, now),
    category: "item",
    lifecycle,
    label: itemType === "unknown" ? `Codex item ${lifecycle}` : `${itemType} ${lifecycle}`,
  });
}

const APPROVAL_METHODS = new Map([
  ["item/commandExecution/requestApproval", "Command approval requested"],
  ["item/fileChange/requestApproval", "File-change approval requested"],
  ["item/permissions/requestApproval", "Permission approval requested"],
  ["applyPatchApproval", "File-change approval requested"],
  ["execCommandApproval", "Command approval requested"],
]);

export function normalizeMessage(
  envelope: ProtocolMethodEnvelope,
  now: () => Date,
): NormalizedMessage {
  const method = envelope.method;
  if (method === "thread/started") {
    const thread = normalizeThread(objectField(envelope.params, "thread"), false, now);
    return thread ? { thread } : {};
  }
  if (method === "thread/status/changed") {
    const threadId = stringField(envelope.params, "threadId");
    return { runtime: { threadId, ...runtimeProjection(objectField(envelope.params, "status")) } };
  }
  if (method === "thread/archived" || method === "thread/unarchived") {
    return {
      archived: {
        threadId: stringField(envelope.params, "threadId"),
        value: method === "thread/archived",
      },
    };
  }
  if (method === "thread/closed") {
    const threadId = stringField(envelope.params, "threadId");
    return {
      activity: activity({
        sourceKey: `thread:${threadId}:closed`,
        threadId,
        occurredAt: now().toISOString(),
        category: "thread",
        lifecycle: "closed",
        label: "Thread closed",
      }),
    };
  }
  if (method === "thread/goal/updated") {
    const threadId = stringField(envelope.params, "threadId");
    const goal = objectField(envelope.params, "goal");
    const status = stringField(goal, "status");
    return {
      activity: activity({
        sourceKey: `goal:${threadId}:${String(goal.updatedAt ?? status)}`,
        threadId,
        turnId: optionalString(envelope.params, "turnId"),
        occurredAt: unixMilliseconds(
          typeof goal.updatedAt === "number" ? goal.updatedAt * 1_000 : null,
          now,
        ),
        category: "goal",
        lifecycle: status,
        label: status === "blocked" ? "Goal blocked" : `Goal ${status}`,
      }),
    };
  }
  if (method === "thread/goal/cleared") {
    const threadId = stringField(envelope.params, "threadId");
    const occurredAt = now().toISOString();
    return {
      activity: activity({
        sourceKey: `goal:${threadId}:cleared:${occurredAt}`,
        threadId,
        occurredAt,
        category: "goal",
        lifecycle: "cleared",
        label: "Goal cleared",
      }),
    };
  }
  if (method === "turn/started" || method === "turn/completed") {
    const threadId = stringField(envelope.params, "threadId");
    const turn = objectField(envelope.params, "turn");
    const turnId = stringField(turn, "id");
    const status =
      method === "turn/started" ? "started" : stringField(turn, "status");
    const timestamp =
      method === "turn/started" ? turn.startedAt : (turn.completedAt ?? turn.startedAt);
    return {
      activity: activity({
        sourceKey: `turn:${threadId}:${turnId}:${status}`,
        threadId,
        turnId,
        occurredAt:
          typeof timestamp === "number" ? unixSeconds(timestamp) : now().toISOString(),
        category: "turn",
        lifecycle: status,
        label: status === "started" ? "Turn started" : `Turn ${status}`,
      }),
    };
  }
  if (method === "item/started" || method === "item/completed") {
    return {
      activity: itemFact(envelope, method === "item/started" ? "started" : "completed", now),
    };
  }
  if (APPROVAL_METHODS.has(method)) {
    const params = envelope.params;
    const threadId =
      isObject(params) && typeof params.threadId === "string"
        ? params.threadId
        : stringField(params, "conversationId");
    const turnId =
      isObject(params) && typeof params.turnId === "string" ? params.turnId : null;
    const itemId =
      isObject(params) && typeof params.itemId === "string" ? params.itemId : null;
    return {
      activity: activity({
        sourceKey: `request:${threadId}:${String(envelope.id)}:pending`,
        threadId,
        turnId,
        itemId,
        occurredAt: unixMilliseconds(
          isObject(params) ? params.startedAtMs : null,
          now,
        ),
        category: "approval",
        lifecycle: "pending",
        label: APPROVAL_METHODS.get(method)!,
      }),
    };
  }
  if (method === "item/tool/requestUserInput" || method === "mcpServer/elicitation/request") {
    const threadId = stringField(envelope.params, "threadId");
    return {
      activity: activity({
        sourceKey: `request:${threadId}:${String(envelope.id)}:pending`,
        threadId,
        turnId: optionalString(envelope.params, "turnId"),
        itemId:
          isObject(envelope.params) && typeof envelope.params.itemId === "string"
            ? envelope.params.itemId
            : null,
        occurredAt: now().toISOString(),
        category: "input_request",
        lifecycle: "pending",
        label:
          method === "item/tool/requestUserInput"
            ? "User input requested"
            : "MCP input requested",
      }),
    };
  }
  if (method === "serverRequest/resolved") {
    const threadId = stringField(envelope.params, "threadId");
    const requestId =
      isObject(envelope.params) &&
      (typeof envelope.params.requestId === "string" ||
        typeof envelope.params.requestId === "number")
        ? envelope.params.requestId
        : (() => {
            throw new Error("Codex App Server requestId field is invalid.");
          })();
    return {
      activity: activity({
        sourceKey: `request:${threadId}:${String(requestId)}:resolved`,
        threadId,
        occurredAt: now().toISOString(),
        category: "input_request",
        lifecycle: "resolved",
        label: "Server request resolved",
      }),
    };
  }
  if (method === "error") {
    const threadId =
      isObject(envelope.params) && typeof envelope.params.threadId === "string"
        ? envelope.params.threadId
        : null;
    return threadId
      ? {
          activity: activity({
            sourceKey: `error:${threadId}:${now().toISOString()}`,
            threadId,
            occurredAt: now().toISOString(),
            category: "error",
            lifecycle: "reported",
            label: "Codex runtime error",
          }),
        }
      : { unknown: true };
  }
  return { unknown: true };
}

export function assertThreadListResponse(value: unknown): {
  data: unknown[];
  nextCursor: string | null;
} {
  if (
    !isObject(value) ||
    !Array.isArray(value.data) ||
    (value.nextCursor !== null && typeof value.nextCursor !== "string")
  ) {
    throw new Error("Codex App Server thread/list response is invalid.");
  }
  return { data: value.data, nextCursor: value.nextCursor as string | null };
}

export function assertThreadReadResponse(value: unknown): JsonObject {
  return objectField(value, "thread");
}
