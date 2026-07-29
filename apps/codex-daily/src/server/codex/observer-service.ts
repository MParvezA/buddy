import { EventEmitter } from "node:events";
import type {
  ObserverConnectionHealth,
  ObserverMode,
  ObserverSnapshot,
  TransientThreadDetail,
} from "../../shared/observer-types.js";
import { ObserverRepository } from "../storage/observer-repository.js";
import {
  assertThreadListResponse,
  assertThreadReadResponse,
  normalizeMessage,
  normalizeThread,
} from "./activity-normalizer.js";
import {
  AppServerClient,
  type ProcessFactory,
} from "./app-server-client.js";
import type { ProtocolMethodEnvelope } from "./app-server-protocol.js";

export interface ObserverServiceOptions {
  repository: ObserverRepository;
  mode?: ObserverMode;
  executable?: string;
  processFactory?: ProcessFactory;
  clock?: () => Date;
  inventoryIntervalMs?: number;
  requestTimeoutMs?: number;
  reconnectBaseMs?: number;
  reconnectMaxMs?: number;
  random?: () => number;
  setTimer?: typeof setTimeout;
  clearTimer?: typeof clearTimeout;
}

export class ObserverUnavailableError extends Error {}
export class ObserverNotFoundError extends Error {}

export class ObserverService extends EventEmitter {
  private readonly repository: ObserverRepository;
  private readonly mode: ObserverMode;
  private readonly executable: string;
  private readonly processFactory?: ProcessFactory;
  private readonly clock: () => Date;
  private readonly inventoryIntervalMs: number;
  private readonly requestTimeoutMs: number;
  private readonly reconnectBaseMs: number;
  private readonly reconnectMaxMs: number;
  private readonly random: () => number;
  private readonly setTimer: typeof setTimeout;
  private readonly clearTimer: typeof clearTimeout;
  private client: AppServerClient | null = null;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private inventoryTimer: ReturnType<typeof setTimeout> | null = null;
  private reconnectAttempt = 0;
  private stopped = true;
  private connecting = false;
  private eventSequence = 0;
  private diagnosticsIgnored = 0;
  private health: ObserverConnectionHealth;

  constructor(options: ObserverServiceOptions) {
    super();
    this.repository = options.repository;
    this.mode = options.mode ?? "standalone_history";
    this.executable = options.executable ?? "codex";
    this.processFactory = options.processFactory;
    this.clock = options.clock ?? (() => new Date());
    this.inventoryIntervalMs = options.inventoryIntervalMs ?? 15_000;
    this.requestTimeoutMs = options.requestTimeoutMs ?? 8_000;
    this.reconnectBaseMs = options.reconnectBaseMs ?? 500;
    this.reconnectMaxMs = options.reconnectMaxMs ?? 30_000;
    this.random = options.random ?? Math.random;
    this.setTimer = options.setTimer ?? setTimeout;
    this.clearTimer = options.clearTimer ?? clearTimeout;
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

  nextEvent(): { id: string; snapshot: ObserverSnapshot } {
    return { id: String(++this.eventSequence), snapshot: this.snapshot() };
  }

  async detail(threadId: string): Promise<TransientThreadDetail> {
    if (this.repository.isExcluded(threadId)) {
      throw new ObserverNotFoundError("The observed thread was not found.");
    }
    const stored = this.repository.findThread(threadId);
    if (!stored) throw new ObserverNotFoundError("The observed thread was not found.");
    if (!this.client || this.health.state !== "connected") {
      throw new ObserverUnavailableError("Codex is not connected for transient detail.");
    }
    const result = await this.client.request("thread/read", {
      threadId,
      includeTurns: true,
    });
    const rawThread = assertThreadReadResponse(result);
    if (rawThread.id !== threadId || !Array.isArray(rawThread.turns)) {
      throw new Error("Codex App Server thread/read response is invalid.");
    }
    return {
      thread: stored,
      // This is intentionally the sole pass-through of sensitive protocol content.
      // No repository method accepts it and snapshot/SSE DTOs cannot contain it.
      turns: rawThread.turns,
      fetchedAt: this.clock().toISOString(),
    };
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
        this.ingest(envelope);
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

  private async refreshInventory(client: AppServerClient): Promise<void> {
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
          if (!thread || this.repository.isExcluded(thread.id)) continue;
          const previous = this.repository.findThread(thread.id);
          thread.lastActivityAt = previous?.lastActivityAt ?? thread.updatedAt;
          if (!this.repository.upsertThread(thread)) continue;
          this.repository.addActivity({
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

  private ingest(envelope: ProtocolMethodEnvelope): void {
    const normalized = normalizeMessage(envelope, this.clock);
    let changed = false;
    if (normalized.thread && !this.repository.isExcluded(normalized.thread.id)) {
      changed = this.repository.upsertThread(normalized.thread) || changed;
    }
    if (normalized.runtime && !this.repository.isExcluded(normalized.runtime.threadId)) {
      this.repository.updateRuntime(
        normalized.runtime.threadId,
        normalized.runtime.runtime,
        normalized.runtime.waitingOnApproval,
        normalized.runtime.waitingOnUserInput,
        this.clock().toISOString(),
      );
      changed = true;
    }
    if (normalized.archived && !this.repository.isExcluded(normalized.archived.threadId)) {
      this.repository.setArchived(
        normalized.archived.threadId,
        normalized.archived.value,
        this.clock().toISOString(),
      );
      changed = true;
    }
    if (normalized.activity) {
      changed = this.repository.addActivity(normalized.activity) || changed;
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
    const delay = Math.round(base * (0.8 + this.random() * 0.4));
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

  private publish(): void {
    this.emit("snapshot", this.nextEvent());
  }
}
