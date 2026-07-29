export type JsonObject = Record<string, unknown>;

export interface ProtocolResponse {
  id: string | number;
  result?: unknown;
  error?: { code?: unknown; message?: unknown };
}

export interface ProtocolMethodEnvelope {
  id?: string | number;
  method: string;
  params?: unknown;
}

export type ProtocolEnvelope = ProtocolResponse | ProtocolMethodEnvelope;

export function isObject(value: unknown): value is JsonObject {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function decodeEnvelope(line: string): ProtocolEnvelope {
  let value: unknown;
  try {
    value = JSON.parse(line);
  } catch {
    throw new Error("Codex App Server emitted invalid JSONL.");
  }
  if (!isObject(value)) throw new Error("Codex App Server emitted a malformed envelope.");
  if (typeof value.method === "string") {
    if (
      value.id !== undefined &&
      typeof value.id !== "string" &&
      typeof value.id !== "number"
    ) {
      throw new Error("Codex App Server emitted a malformed request ID.");
    }
    return value as unknown as ProtocolMethodEnvelope;
  }
  if (
    (typeof value.id === "string" || typeof value.id === "number") &&
    ("result" in value || "error" in value)
  ) {
    return value as unknown as ProtocolResponse;
  }
  throw new Error("Codex App Server emitted a malformed envelope.");
}

export function objectField(value: unknown, name: string): JsonObject {
  if (!isObject(value) || !isObject(value[name])) {
    throw new Error(`Codex App Server ${name} field is invalid.`);
  }
  return value[name] as JsonObject;
}

export function stringField(value: unknown, name: string): string {
  if (!isObject(value) || typeof value[name] !== "string" || !value[name]) {
    throw new Error(`Codex App Server ${name} field is invalid.`);
  }
  return value[name] as string;
}

export function optionalString(value: unknown, name: string): string | null {
  if (!isObject(value) || value[name] == null) return null;
  if (typeof value[name] !== "string") {
    throw new Error(`Codex App Server ${name} field is invalid.`);
  }
  return value[name] as string;
}

export function unixSeconds(value: unknown): string {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    throw new Error("Codex App Server timestamp is invalid.");
  }
  return new Date(value * 1_000).toISOString();
}

export function unixMilliseconds(value: unknown, fallback: () => Date): string {
  return typeof value === "number" && Number.isFinite(value)
    ? new Date(value).toISOString()
    : fallback().toISOString();
}
