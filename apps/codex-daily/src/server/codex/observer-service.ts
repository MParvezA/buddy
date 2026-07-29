import { EventEmitter } from "node:events";
import { randomUUID } from "node:crypto";
import type {
  ObserverConnectionHealth,
  ObserverMode,
  ObserverSnapshot,
  ThreadDetail,
} from "../../shared/observer-types.js";
import type { ObserverOperationalDiagnostics } from "../../shared/operations.js";
import { ObserverRepository } from "../storage/observer-repository.js";
import {
  assertThreadListResponse,
  assertThreadReadResponse,
  normalizeMessage,
  normalizeThread,
} from "./activity-normalizer.js";
import {
  AppServerClient,
  AppServerRequestError,
  type ProcessFactory,
} from "./app-server-client.js";
import {
  isObject,
  type ProtocolMethodEnvelope,
  unixSeconds,
} from "./app-server-protocol.js";

export interface ObserverServiceOptions {
  repository: ObserverRepository;
  mode?: ObserverMode;
  executable?: string;
  processFactory?: ProcessFactory;
  clock?: () => Date;
  inventoryIntervalMs?: number;
  requestTimeoutMs?: number;
  reportingTurnTimeoutMs?: number;
  reconnectBaseMs?: number;
  reconnectMaxMs?: number;
  random?: () => number;
  setTimer?: typeof setTimeout;
  clearTimer?: typeof clearTimeout;
  processInstanceId?: string;
}

export class ObserverUnavailableError extends Error {}
export class ObserverNotFoundError extends Error {}
export class ObserverInternalTurnError extends Error {
  constructor(readonly category: "timeout" | "refusal" | "invalid_output" | "unavailable") {
    super(`Codex internal turn failed (${category}).`);
    this.name = "ObserverInternalTurnError";
  }
}
export const DEFAULT_REPORTING_TURN_TIMEOUT_MS = 120_000;
export const DEFAULT_SESSION_BRIEF_TURN_TIMEOUT_MS = 120_000;

export class ObserverService extends EventEmitter {
  private readonly repository: ObserverRepository;
  private readonly mode: ObserverMode;
  private readonly executable: string;
  private readonly processFactory?: ProcessFactory;
  private readonly clock: () => Date;
  private readonly inventoryIntervalMs: number;
  private readonly requestTimeoutMs: number;
  private readonly reportingTurnTimeoutMs: number;
  private readonly reconnectBaseMs: number;
  private readonly reconnectMaxMs: number;
  private readonly random: () => number;
  private readonly setTimer: typeof setTimeout;
  private readonly clearTimer: typeof clearTimeout;
  private readonly processInstanceId: string;
  private client: AppServerClient | null = null;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private inventoryTimer: ReturnType<typeof setTimeout> | null = null;
  private reconnectAttempt = 0;
  private stopped = true;
  private connecting = false;
  private eventSequence = 0;
  private diagnosticsIgnored = 0;
  private diagnosticsReplayed = 0;
  private reconnectBackoffMs: number | null = null;
  private lastErrorCategory: string | null = null;
  private lastErrorAt: string | null = null;
  private health: ObserverConnectionHealth;
  private internalThreadCreationBuffer:
    | Array<{
        envelope: ProtocolMethodEnvelope;
        requestEpisodeNamespace: string;
      }>
    | null = null;
  private reportingThreadCreation: Promise<string> | null = null;
  private inventoryCreationTail: Promise<void> = Promise.resolve();
  private readonly ephemeralInternalThreadIds = new Set<string>();
  private connectionGeneration = 0;

  constructor(options: ObserverServiceOptions) {
    super();
    this.repository = options.repository;
    this.mode = options.mode ?? "standalone_history";
    this.executable = options.executable ?? "codex";
    this.processFactory = options.processFactory;
    this.clock = options.clock ?? (() => new Date());
    this.inventoryIntervalMs = options.inventoryIntervalMs ?? 15_000;
    this.requestTimeoutMs = options.requestTimeoutMs ?? 8_000;
    this.reportingTurnTimeoutMs =
      options.reportingTurnTimeoutMs ?? DEFAULT_REPORTING_TURN_TIMEOUT_MS;
    if (
      !Number.isFinite(this.reportingTurnTimeoutMs) ||
      this.reportingTurnTimeoutMs <= 0 ||
      this.reportingTurnTimeoutMs > 600_000
    ) {
      throw new Error("Reporting turn timeout must be between 1 and 600000 milliseconds.");
    }
    this.reconnectBaseMs = options.reconnectBaseMs ?? 500;
    this.reconnectMaxMs = options.reconnectMaxMs ?? 30_000;
    if (
      !Number.isFinite(this.reconnectBaseMs) ||
      !Number.isFinite(this.reconnectMaxMs) ||
      this.reconnectBaseMs <= 0 ||
      this.reconnectMaxMs <= 0 ||
      this.reconnectMaxMs > 300_000
    ) {
      throw new Error(
        "Reconnect timing must be positive and capped at 300000 milliseconds.",
      );
    }
    this.random = options.random ?? Math.random;
    this.setTimer = options.setTimer ?? setTimeout;
    this.clearTimer = options.clearTimer ?? clearTimeout;
    this.processInstanceId = options.processInstanceId ?? randomUUID();
    if (
      !/^[A-Za-z0-9._-]{1,100}$/.test(this.processInstanceId)
    ) {
      throw new Error("Observer process instance ID is invalid.");
    }
    this.health = {
      state: "disconnected",
      capability: this.mode,
      lastSuccessfulSyncAt: null,
      lastInventoryRefreshAt: null,
      diagnostic: null,
    };
  }

  async start(): Promise<void> {
    if (!this.stopped) return;
    this.stopped = false;
    this.health = { ...this.health, state: "connecting", diagnostic: null };
    this.publish();
    await this.connect();
  }

  async stop(): Promise<void> {
    this.stopped = true;
    if (this.reconnectTimer) this.clearTimer(this.reconnectTimer);
    if (this.inventoryTimer) this.clearTimer(this.inventoryTimer);
    this.reconnectTimer = null;
    this.inventoryTimer = null;
    const client = this.client;
    this.client = null;
    await client?.stop();
    this.health = { ...this.health, state: "disconnected", diagnostic: null };
    this.publish();
  }

  snapshot(): ObserverSnapshot {
    return {
      health: { ...this.health },
      threads: this.repository.listThreads(),
      activities: this.repository.listActivities(),
      taskLinks: this.repository.listLinks(),
    };
  }

  operationalDiagnostics(): ObserverOperationalDiagnostics {
    return {
      state: this.health.state,
      lastSuccessfulSyncAt: this.health.lastSuccessfulSyncAt,
      reconnectAttempt: this.reconnectAttempt,
      reconnectBackoffMs: this.reconnectBackoffMs,
      lastErrorCategory: this.lastErrorCategory,
      lastErrorAt: this.lastErrorAt,
      replayedEventCount: this.diagnosticsReplayed,
      ignoredEventCount: this.diagnosticsIgnored,
    };
  }

  nextEvent(): { id: string; snapshot: ObserverSnapshot } {
    return { id: String(++this.eventSequence), snapshot: this.snapshot() };
  }

  async detail(threadId: string): Promise<ThreadDetail> {
    if (this.repository.isExcluded(threadId)) {
      throw new ObserverNotFoundError("The observed thread was not found.");
    }
    const stored = this.repository.findThread(threadId);
    if (!stored) throw new ObserverNotFoundError("The observed thread was not found.");
    const retained = {
      thread: stored,
      activities: this.repository.listActivitiesForThread(threadId),
    };
    if (!this.client || this.health.state !== "connected") {
      return {
        ...retained,
        transientHistory: {
          status: "unavailable",
          reason: "Codex is disconnected; full history is unavailable.",
        },
      };
    }
    try {
      const result = await this.client.request("thread/read", {
        threadId,
        includeTurns: true,
      });
      const rawThread = assertThreadReadResponse(result);
      if (rawThread.id !== threadId || !Array.isArray(rawThread.turns)) {
        throw new Error("Codex App Server thread/read response is invalid.");
      }
      return {
        ...retained,
        transientHistory: {
          status: "available",
          // This is intentionally the sole pass-through of sensitive protocol
          // content. No repository method accepts it and snapshot/SSE DTOs
          // cannot contain it.
          turns: rawThread.turns,
          fetchedAt: this.clock().toISOString(),
        },
      };
    } catch {
      return {
        ...retained,
        transientHistory: {
          status: "unavailable",
          reason: "Full history could not be fetched from Codex right now.",
        },
      };
    }
  }

  async ensureReportingThread(
    existingThreadId: string | null,
    register: (threadId: string) => void,
  ): Promise<string> {
    if (existingThreadId) {
      this.repository.exclude(existingThreadId, this.clock().toISOString());
      register(existingThreadId);
      return existingThreadId;
    }
    if (this.reportingThreadCreation) {
      const threadId = await this.reportingThreadCreation;
      register(threadId);
      return threadId;
    }
    const creation = this.createReportingThread(register);
    this.reportingThreadCreation = creation;
    try {
      return await creation;
    } finally {
      if (this.reportingThreadCreation === creation) {
        this.reportingThreadCreation = null;
      }
    }
  }

  private createReportingThread(register: (threadId: string) => void): Promise<string> {
    return this.withInventoryCreationLock(() =>
      this.createReportingThreadLocked(register),
    );
  }

  private async createReportingThreadLocked(
    register: (threadId: string) => void,
  ): Promise<string> {
    const client = this.connectedClient();
    this.internalThreadCreationBuffer = [];
    try {
      const result = await client.requestInternal("thread/start", {
        cwd: process.cwd(),
        approvalPolicy: "never",
        sandbox: "read-only",
        experimentalRawEvents: false,
      });
      const value = result as { thread?: { id?: unknown } };
      const id = value?.thread?.id;
      if (typeof id !== "string" || !id) {
        throw new Error("Codex reporting thread creation returned an invalid result.");
      }
      // Registration and exclusion happen before buffered App Server
      // notifications are considered by the ordinary observer.
      this.repository.exclude(id, this.clock().toISOString());
      register(id);
      this.replayInternalCreationBuffer(id);
      return id;
    } catch (error) {
      this.replayInternalCreationBuffer(null);
      throw error;
    }
  }

  async readSessionBriefSource(
    threadId: string,
    signal?: AbortSignal,
  ): Promise<{ turns: unknown[]; sourceUpdatedAt: string }> {
    if (this.repository.isExcluded(threadId) || this.ephemeralInternalThreadIds.has(threadId)) {
      throw new ObserverNotFoundError("The observed thread was not found.");
    }
    const client = this.connectedClient();
    let result: unknown;
    try {
      result = await client.request(
        "thread/read",
        { threadId, includeTurns: true },
        signal,
      );
    } catch (error) {
      if (
        error instanceof AppServerRequestError &&
        error.category === "rejected"
      ) {
        throw new ObserverNotFoundError("The observed thread was not found.");
      }
      throw error;
    }
    const raw = assertThreadReadResponse(result);
    if (
      raw.id !== threadId ||
      !Array.isArray(raw.turns)
    ) {
      throw new ObserverInternalTurnError("invalid_output");
    }
    const sourceUpdatedAt = unixSeconds(raw.updatedAt);
    const stored = this.repository.findThread(threadId);
    if (stored && stored.updatedAt !== sourceUpdatedAt) {
      const normalized = normalizeThread(raw, stored.archived, this.clock);
      if (!normalized || normalized.id !== threadId) {
        throw new ObserverInternalTurnError("invalid_output");
      }
      if (this.repository.upsertThread(normalized)) this.publish();
    }
    return {
      turns: raw.turns,
      sourceUpdatedAt,
    };
  }

  async createSessionBriefAnalysisThread(signal?: AbortSignal): Promise<string> {
    return this.withInventoryCreationLock(async () => {
      const client = this.connectedClient();
      this.internalThreadCreationBuffer = [];
      let candidateThreadId: string | null = null;
      try {
        const result = await client.requestInternal(
          "thread/start",
          {
            model: "gpt-5.6-sol",
            allowProviderModelFallback: false,
            ephemeral: true,
            approvalPolicy: "never",
            dynamicTools: [],
            environments: [],
            runtimeWorkspaceRoots: [],
            cwd: null,
            experimentalRawEvents: false,
          },
          signal,
        );
        const value = result as {
          model?: unknown;
          thread?: { id?: unknown; ephemeral?: unknown };
        };
        const thread = value?.thread;
        const id = thread?.id;
        candidateThreadId =
          typeof id === "string" && id ? id : null;
        if (
          !candidateThreadId ||
          value.model !== "gpt-5.6-sol" ||
          thread?.ephemeral !== true
        ) {
          throw new ObserverInternalTurnError("invalid_output");
        }
        this.ephemeralInternalThreadIds.add(candidateThreadId);
        this.replayInternalCreationBuffer(candidateThreadId);
        return candidateThreadId;
      } catch (error) {
        this.replayInternalCreationBuffer(candidateThreadId, true);
        throw error;
      }
    });
  }

  runSessionBriefAnalysisTurn(
    threadId: string,
    prompt: string,
    outputSchema: Record<string, unknown>,
    signal?: AbortSignal,
    timeoutMs = DEFAULT_SESSION_BRIEF_TURN_TIMEOUT_MS,
  ): Promise<string> {
    if (!this.ephemeralInternalThreadIds.has(threadId)) {
      return Promise.reject(new ObserverInternalTurnError("unavailable"));
    }
    return this.runInternalTurn(
      threadId,
      {
        threadId,
        model: "gpt-5.6-sol",
        effort: "medium",
        environments: [],
        input: [{ type: "text", text: prompt }],
        outputSchema,
      },
      timeoutMs,
      signal,
    );
  }

  async readFinalAssistantMessage(threadId: string): Promise<string | null> {
    if (this.repository.isExcluded(threadId)) return null;
    const client = this.connectedClient();
    const result = await client.request("thread/read", {
      threadId,
      includeTurns: true,
    });
    const raw = assertThreadReadResponse(result);
    if (!Array.isArray(raw.turns)) {
      throw new Error("Codex App Server thread/read response is invalid.");
    }
    return finalAssistantText(raw.turns);
  }

  async runReportingTurn(threadId: string, prompt: string): Promise<string> {
    if (!this.repository.isExcluded(threadId)) {
      throw new Error("The reporting thread is not durably excluded.");
    }
    try {
      return await this.runInternalTurn(
        threadId,
        { threadId, input: [{ type: "text", text: prompt }] },
        this.reportingTurnTimeoutMs,
      );
    } catch (error) {
      if (error instanceof ObserverInternalTurnError && error.category === "timeout") {
        throw new Error("Codex reporting turn timed out.");
      }
      throw new Error("Codex reporting turn returned no final assistant message.");
    }
  }

  private async runInternalTurn(
    threadId: string,
    params: Record<string, unknown>,
    timeoutMs: number,
    signal?: AbortSignal,
  ): Promise<string> {
    const client = this.connectedClient();
    let expectedTurnId: string | null = null;
    const buffered = new Map<string, unknown>();
    let settle:
      | { resolve: (text: string) => void; reject: (error: Error) => void }
      | null = null;
    let finished = false;
    const cleanup = () => {
      client.off("message", listener);
      this.clearTimer(timer);
      signal?.removeEventListener("abort", abortListener);
    };
    const finish = (turn: unknown) => {
      if (finished) return;
      const text = exactCompletedAssistantText(turn, expectedTurnId);
      finished = true;
      cleanup();
      if (text) settle?.resolve(text);
      else settle?.reject(new ObserverInternalTurnError("refusal"));
    };
    const listener = (envelope: ProtocolMethodEnvelope) => {
      if (envelope.method !== "turn/completed") return;
      const envelopeThreadId = protocolThreadId(envelope);
      if (envelopeThreadId !== threadId) return;
      const params = envelope.params as { turn?: unknown };
      const id = protocolTurnId(params?.turn);
      if (!id) return;
      if (expectedTurnId === id) finish(params.turn);
      else buffered.set(id, params.turn);
    };
    const timer = this.setTimer(() => {
      if (finished) return;
      finished = true;
      cleanup();
      settle?.reject(new ObserverInternalTurnError("timeout"));
    }, timeoutMs);
    const abortListener = () => {
      if (finished) return;
      finished = true;
      cleanup();
      settle?.reject(new ObserverInternalTurnError("unavailable"));
    };
    signal?.addEventListener("abort", abortListener, { once: true });
    client.on("message", listener);
    const completion = new Promise<string>((resolve, reject) => {
      settle = { resolve, reject };
    });
    try {
      const result = await client.requestInternal("turn/start", params, signal);
      const value = result as { turn?: unknown };
      expectedTurnId = protocolTurnId(value?.turn);
      if (!expectedTurnId) throw new ObserverInternalTurnError("invalid_output");
      const early = buffered.get(expectedTurnId);
      if (early) finish(early);
      return await completion;
    } catch (error) {
      if (!finished) {
        finished = true;
        cleanup();
      }
      throw error;
    }
  }

  link(taskId: string, threadId: string): "linked" | "missing_task" | "missing_thread" {
    const result = this.repository.link(taskId, threadId, this.clock().toISOString());
    if (result === "linked") this.publish();
    return result;
  }

  unlink(taskId: string, threadId: string): "unlinked" | "missing_task" | "missing_thread" {
    const result = this.repository.unlink(taskId, threadId);
    if (result === "unlinked") this.publish();
    return result;
  }

  private connectedClient(): AppServerClient {
    if (!this.client || this.health.state !== "connected") {
      throw new ObserverUnavailableError("Codex is not connected for reporting.");
    }
    return this.client;
  }

  private async connect(): Promise<void> {
    if (this.stopped || this.connecting) return;
    this.connecting = true;
    const args =
      this.mode === "standalone_history" ? ["app-server", "--stdio"] : ["app-server", "proxy"];
    const client = new AppServerClient({
      executable: this.executable,
      args,
      processFactory: this.processFactory,
      requestTimeoutMs: this.requestTimeoutMs,
      setTimer: this.setTimer,
      clearTimer: this.clearTimer,
    });
    const requestEpisodeNamespace =
      `${this.processInstanceId}:connection-${++this.connectionGeneration}`;
    this.client = client;
    let failed = false;
    const disconnect = (error: Error) => {
      if (failed || this.stopped || this.client !== client) return;
      failed = true;
      void this.connectionFailed(client, error);
    };
    client.on("disconnect", disconnect);
    client.on("protocolError", disconnect);
    client.on("message", (envelope: ProtocolMethodEnvelope) => {
      try {
        if (this.internalThreadCreationBuffer) {
          this.internalThreadCreationBuffer.push({
            envelope,
            requestEpisodeNamespace,
          });
          return;
        }
        this.ingest(envelope, requestEpisodeNamespace);
      } catch (error) {
        disconnect(
          error instanceof Error
            ? error
            : new Error("Codex App Server emitted an invalid known event."),
        );
      }
    });

    try {
      await client.start();
      await this.refreshInventory(client);
      if (failed || this.stopped || this.client !== client) return;
      const syncedAt = this.clock().toISOString();
      this.reconnectAttempt = 0;
      this.reconnectBackoffMs = null;
      this.health = {
        ...this.health,
        state: "connected",
        lastSuccessfulSyncAt: syncedAt,
        lastInventoryRefreshAt: syncedAt,
        diagnostic:
          this.mode === "standalone_history"
            ? "History polling is connected; live requests from other Codex processes may not be visible."
            : null,
      };
      this.publish();
      this.scheduleInventory(client);
    } catch (error) {
      disconnect(error instanceof Error ? error : new Error("Codex connection failed."));
    } finally {
      this.connecting = false;
    }
  }

  private replayInternalCreationBuffer(
    internalThreadId: string | null,
    suppressEphemeralStarted = false,
  ): void {
    const buffered = this.internalThreadCreationBuffer ?? [];
    this.internalThreadCreationBuffer = null;
    const ephemeralThreadIds = new Set<string>();
    if (suppressEphemeralStarted) {
      for (const { envelope } of buffered) {
        if (envelope.method !== "thread/started" || !isObject(envelope.params)) {
          continue;
        }
        const thread = envelope.params.thread;
        if (
          isObject(thread) &&
          thread.ephemeral === true &&
          typeof thread.id === "string"
        ) {
          ephemeralThreadIds.add(thread.id);
        }
      }
    }
    for (const { envelope, requestEpisodeNamespace } of buffered) {
      const envelopeThreadId = protocolThreadId(envelope);
      if (
        (internalThreadId && envelopeThreadId === internalThreadId) ||
        (envelopeThreadId && ephemeralThreadIds.has(envelopeThreadId))
      ) {
        continue;
      }
      this.ingest(envelope, requestEpisodeNamespace);
    }
  }

  private refreshInventory(client: AppServerClient): Promise<void> {
    return this.withInventoryCreationLock(() =>
      this.refreshInventoryLocked(client),
    );
  }

  private async refreshInventoryLocked(client: AppServerClient): Promise<void> {
    for (const archived of [false, true]) {
      let cursor: string | null = null;
      do {
        const response = assertThreadListResponse(
          await client.request("thread/list", {
            cursor,
            limit: 100,
            sortKey: "updated_at",
            sortDirection: "desc",
            sourceKinds: ["cli", "vscode", "appServer"],
            archived,
          }),
        );
        for (const value of response.data) {
          const thread = normalizeThread(value, archived, this.clock);
          if (
            !thread ||
            this.repository.isExcluded(thread.id) ||
            this.ephemeralInternalThreadIds.has(thread.id)
          ) continue;
          const previous = this.repository.findThread(thread.id);
          thread.lastActivityAt = previous?.lastActivityAt ?? thread.updatedAt;
          if (!this.repository.upsertThread(thread)) continue;
          this.addActivity({
            sourceKey: `thread:${thread.id}:inventory:${thread.updatedAt}:${Number(archived)}`,
            threadId: thread.id,
            turnId: null,
            itemId: null,
            occurredAt: thread.updatedAt,
            category: "thread",
            lifecycle: archived ? "archived" : "observed",
            label: archived ? "Archived thread observed" : "Thread observed",
          });
        }
        cursor = response.nextCursor;
      } while (cursor);
    }
    const syncedAt = this.clock().toISOString();
    this.health = {
      ...this.health,
      lastSuccessfulSyncAt: syncedAt,
      lastInventoryRefreshAt: syncedAt,
    };
  }

  private async withInventoryCreationLock<T>(work: () => Promise<T>): Promise<T> {
    const previous = this.inventoryCreationTail;
    let release = () => {};
    this.inventoryCreationTail = new Promise<void>((resolve) => {
      release = resolve;
    });
    await previous;
    try {
      return await work();
    } finally {
      release();
    }
  }

  private ingest(
    envelope: ProtocolMethodEnvelope,
    requestEpisodeNamespace?: string,
  ): void {
    const normalized = normalizeMessage(
      envelope,
      this.clock,
      requestEpisodeNamespace,
    );
    let changed = false;
    if (
      normalized.thread &&
      !this.repository.isExcluded(normalized.thread.id) &&
      !this.ephemeralInternalThreadIds.has(normalized.thread.id)
    ) {
      changed = this.repository.upsertThread(normalized.thread, true) || changed;
    }
    if (
      normalized.runtime &&
      !this.repository.isExcluded(normalized.runtime.threadId) &&
      !this.ephemeralInternalThreadIds.has(normalized.runtime.threadId)
    ) {
      this.repository.updateRuntime(
        normalized.runtime.threadId,
        normalized.runtime.runtime,
        normalized.runtime.waitingOnApproval,
        normalized.runtime.waitingOnUserInput,
        this.clock().toISOString(),
      );
      changed = true;
    }
    if (
      normalized.archived &&
      !this.repository.isExcluded(normalized.archived.threadId) &&
      !this.ephemeralInternalThreadIds.has(normalized.archived.threadId)
    ) {
      this.repository.setArchived(
        normalized.archived.threadId,
        normalized.archived.value,
        this.clock().toISOString(),
      );
      changed = true;
    }
    if (
      normalized.activity &&
      !this.ephemeralInternalThreadIds.has(normalized.activity.threadId)
    ) {
      changed = this.addActivity(normalized.activity) || changed;
    }
    if (normalized.unknown) this.diagnosticsIgnored += 1;
    if (changed) this.publish();
  }

  private scheduleInventory(client: AppServerClient): void {
    if (this.stopped || this.client !== client) return;
    if (this.inventoryTimer) this.clearTimer(this.inventoryTimer);
    this.inventoryTimer = this.setTimer(() => {
      void this.refreshInventory(client)
        .then(() => {
          if (this.client === client && !this.stopped) {
            this.publish();
            this.scheduleInventory(client);
          }
        })
        .catch((error: unknown) => {
          void this.connectionFailed(
            client,
            error instanceof Error ? error : new Error("Inventory refresh failed."),
          );
        });
    }, this.inventoryIntervalMs);
  }

  private async connectionFailed(client: AppServerClient, error: Error): Promise<void> {
    if (this.client !== client || this.stopped) return;
    this.client = null;
    if (this.inventoryTimer) this.clearTimer(this.inventoryTimer);
    this.inventoryTimer = null;
    await client.stop();
    if (this.stopped) return;
    this.reconnectAttempt += 1;
    this.lastErrorCategory = this.errorCategory(error);
    this.lastErrorAt = this.clock().toISOString();
    this.health = {
      ...this.health,
      state: "reconnecting",
      diagnostic: this.safeDiagnostic(error),
    };
    this.publish();
    const base = Math.min(
      this.reconnectMaxMs,
      this.reconnectBaseMs * 2 ** Math.max(0, this.reconnectAttempt - 1),
    );
    const delay = Math.min(
      this.reconnectMaxMs,
      Math.round(base * (0.8 + this.random() * 0.4)),
    );
    this.reconnectBackoffMs = delay;
    this.reconnectTimer = this.setTimer(() => {
      this.reconnectTimer = null;
      void this.connect();
    }, delay);
  }

  private safeDiagnostic(error: Error): string {
    if (error.message.includes("timed out")) return "Codex App Server did not respond in time.";
    if (error.message.includes("invalid") || error.message.includes("malformed")) {
      return "Codex App Server sent incompatible protocol data.";
    }
    if (this.mode === "shared_live") {
      return "The operator-managed shared App Server is unavailable.";
    }
    return "The local Codex App Server is unavailable; cached activity remains visible.";
  }

  private errorCategory(error: Error): string {
    if (error.message.includes("timed out")) return "timeout";
    if (error.message.includes("invalid") || error.message.includes("malformed")) {
      return "protocol";
    }
    return "unavailable";
  }

  private addActivity(activity: Parameters<ObserverRepository["addActivity"]>[0]): boolean {
    const replayed = this.repository.activityExists(activity.sourceKey);
    const changed = this.repository.addActivity(activity);
    if (replayed) this.diagnosticsReplayed += 1;
    return changed;
  }

  private publish(): void {
    this.emit("snapshot", this.nextEvent());
  }
}

function finalAssistantText(values: unknown[]): string | null {
  const visit = (value: unknown): string | null => {
    if (!value || typeof value !== "object") return null;
    if (Array.isArray(value)) {
      for (let index = value.length - 1; index >= 0; index -= 1) {
        const found = visit(value[index]);
        if (found) return found;
      }
      return null;
    }
    const record = value as Record<string, unknown>;
    const type = typeof record.type === "string" ? record.type : "";
    const role = typeof record.role === "string" ? record.role : "";
    const assistant = role === "assistant" || ["agentMessage", "assistantMessage"].includes(type);
    if (assistant) {
      for (const field of ["text", "message"]) {
        if (typeof record[field] === "string" && record[field]) return record[field] as string;
      }
      if (Array.isArray(record.content)) {
        const text = record.content
          .filter(
            (item): item is Record<string, unknown> =>
              Boolean(item) && typeof item === "object" && !Array.isArray(item),
          )
          .map((item) =>
            typeof item.text === "string" &&
            ["text", "output_text", "input_text"].includes(String(item.type ?? "text"))
              ? item.text
              : "",
          )
          .filter(Boolean)
          .join("\n");
        if (text) return text;
      }
    }
    for (const field of ["items", "content", "turns", "turn", "result"]) {
      const found = visit(record[field]);
      if (found) return found;
    }
    return null;
  };
  return visit(values);
}

function protocolThreadId(envelope: ProtocolMethodEnvelope): string | null {
  const params = envelope.params;
  if (!params || typeof params !== "object" || Array.isArray(params)) return null;
  const record = params as Record<string, unknown>;
  if (typeof record.threadId === "string") return record.threadId;
  if (record.thread && typeof record.thread === "object" && !Array.isArray(record.thread)) {
    const id = (record.thread as Record<string, unknown>).id;
    return typeof id === "string" ? id : null;
  }
  return null;
}

function protocolTurnId(value: unknown): string | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  const id = (value as Record<string, unknown>).id;
  return typeof id === "string" && id ? id : null;
}

function exactCompletedAssistantText(
  turn: unknown,
  expectedTurnId: string | null,
): string | null {
  if (
    !turn ||
    typeof turn !== "object" ||
    Array.isArray(turn) ||
    protocolTurnId(turn) !== expectedTurnId
  ) {
    return null;
  }
  const record = turn as Record<string, unknown>;
  if (record.status !== "completed" || !Array.isArray(record.items)) return null;
  for (let index = record.items.length - 1; index >= 0; index -= 1) {
    const item = record.items[index];
    if (
      item &&
      typeof item === "object" &&
      !Array.isArray(item) &&
      (item as Record<string, unknown>).type === "agentMessage" &&
      typeof (item as Record<string, unknown>).text === "string" &&
      (item as Record<string, unknown>).text
    ) {
      return (item as Record<string, unknown>).text as string;
    }
  }
  return null;
}
