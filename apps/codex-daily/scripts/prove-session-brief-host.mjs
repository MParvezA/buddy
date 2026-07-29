#!/usr/bin/env node
import { spawnSync } from "node:child_process";

const MODEL = "gpt-5.6-sol";
const EFFORT = "medium";
const SYNTHETIC_PROMPT = `Create one operational brief from this invented test chat.
Return only the JSON object required by the output schema.
Allowed evidence labels: user:first-intent, assistant:recent-1

BEGIN INVENTED TEST CHAT DATA
[user:first-intent] USER
Draft a fictional release checklist for the Northstar demo.

[assistant:recent-1] ASSISTANT
The fictional checklist is drafted; the operator should review its dates.
END INVENTED TEST CHAT DATA`;

function fixedSummary(status, category, elapsedMs, cliVersion = "unknown") {
  const safeVersion = /^[A-Za-z0-9._ -]{1,100}$/.test(cliVersion)
    ? cliVersion.replaceAll(" ", "_")
    : "unknown";
  return [
    `status=${status}`,
    `category=${category}`,
    `cli=${safeVersion}`,
    `model=${MODEL}`,
    `effort=${EFFORT}`,
    "synthetic_only=true",
    "history_read=false",
    "ephemeral=true",
    "provider_fallback=false",
    "tools=false",
    "workspace=false",
    "structured_output=true",
    `elapsed_ms=${elapsedMs}`,
  ].join(" ");
}

function object(value) {
  return value && typeof value === "object" && !Array.isArray(value)
    ? value
    : null;
}

function completionText(envelope, threadId, turnId) {
  if (envelope.method !== "turn/completed") return null;
  const params = object(envelope.params);
  const turn = object(params?.turn);
  if (
    params?.threadId !== threadId ||
    turn?.id !== turnId ||
    turn?.status !== "completed" ||
    !Array.isArray(turn.items)
  ) {
    return null;
  }
  const final = [...turn.items].reverse().find((item) => {
    const value = object(item);
    return value?.type === "agentMessage" && typeof value.text === "string";
  });
  const value = object(final);
  return typeof value?.text === "string" ? value.text : null;
}

class HostProofModelContractError extends Error {
  constructor() {
    super("The installed host did not satisfy the session-brief model contract.");
    this.name = "HostProofModelContractError";
  }
}

function safeCategory(error) {
  if (error instanceof HostProofModelContractError) {
    return "model_contract_failed";
  }
  if (
    error instanceof Error &&
    error.name === "AppServerRequestError" &&
    (error.category === "rejected" || error.category === "unavailable")
  ) {
    return error.category === "rejected"
      ? "request_rejected"
      : "host_unavailable";
  }
  return "host_unavailable";
}

if (process.env.CODEX_DAILY_RUN_HOST_MODEL_PROOF !== "1") {
  process.stderr.write(
    `${fixedSummary("blocked", "opt_in_required", 0)}\n`,
  );
  process.exit(2);
}

const startedAt = Date.now();
const executable = process.env.CODEX_DAILY_CODEX_PATH || "codex";
const versionResult = spawnSync(executable, ["--version"], {
  encoding: "utf8",
  timeout: 10_000,
  shell: false,
});
const cliVersion =
  versionResult.status === 0
    ? versionResult.stdout.trim().slice(0, 100)
    : "unavailable";
const completionEnvelopes = [];
let client;

try {
  const {
    AppServerClient,
  } = await import("../dist/server/server/codex/app-server-client.js");
  const {
    parseSessionBriefOutput,
    sessionBriefOutputSchema,
  } = await import("../dist/server/server/briefs/session-brief-output.js");
  client = new AppServerClient({
    executable,
    args: ["app-server", "--stdio"],
    requestTimeoutMs: 120_000,
  });
  client.on("message", (envelope) => {
    if (envelope.method === "turn/completed") completionEnvelopes.push(envelope);
  });
  await client.start();
  const startResult = object(
    await client.requestInternal("thread/start", {
      model: MODEL,
      ephemeral: true,
      allowProviderModelFallback: false,
      dynamicTools: [],
      environments: [],
      runtimeWorkspaceRoots: [],
      cwd: null,
      approvalPolicy: "never",
      experimentalRawEvents: false,
    }),
  );
  const thread = object(startResult?.thread);
  if (
    startResult?.model !== MODEL ||
    thread?.ephemeral !== true ||
    typeof thread.id !== "string" ||
    !thread.id
  ) {
    throw new HostProofModelContractError();
  }

  const evidence = ["user:first-intent", "assistant:recent-1"];
  const turnResult = object(
    await client.requestInternal("turn/start", {
      threadId: thread.id,
      model: MODEL,
      effort: EFFORT,
      environments: [],
      input: [{ type: "text", text: SYNTHETIC_PROMPT }],
      outputSchema: sessionBriefOutputSchema(evidence),
    }),
  );
  const turn = object(turnResult?.turn);
  if (typeof turn?.id !== "string" || !turn.id) {
    throw new HostProofModelContractError();
  }

  const raw = await new Promise((resolve, reject) => {
    const buffered = completionEnvelopes
      .map((envelope) => completionText(envelope, thread.id, turn.id))
      .find((text) => text !== null);
    if (buffered !== undefined) {
      resolve(buffered);
      return;
    }
    const timeout = setTimeout(() => {
      client.off("message", listener);
      reject(new DOMException("Timed out", "AbortError"));
    }, 120_000);
    const listener = (envelope) => {
      const text = completionText(envelope, thread.id, turn.id);
      if (text === null) return;
      clearTimeout(timeout);
      client.off("message", listener);
      resolve(text);
    };
    client.on("message", listener);
  });
  try {
    parseSessionBriefOutput(raw, evidence);
  } catch {
    throw new HostProofModelContractError();
  }
  process.stdout.write(
    `${fixedSummary("passed", "ok", Date.now() - startedAt, cliVersion)}\n`,
  );
} catch (error) {
  process.stderr.write(
    `${fixedSummary(
      "blocked",
      safeCategory(error),
      Date.now() - startedAt,
      cliVersion,
    )}\n`,
  );
  process.exitCode = 1;
} finally {
  await client?.stop().catch(() => undefined);
}
