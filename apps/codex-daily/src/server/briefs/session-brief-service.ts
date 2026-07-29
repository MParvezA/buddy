import { EventEmitter } from "node:events";
import type {
  ObservedThread,
  ObserverSnapshot,
} from "../../shared/observer-types.js";
import type {
  SessionBriefItem,
  SessionBriefSnapshot,
  SessionBriefSseEvent,
} from "../../shared/session-briefs.js";
import type { ObserverService } from "../codex/observer-service.js";
import type { SessionBriefAnalyzer } from "./placeholder-brief-analyzer.js";
import {
  SessionBriefRepository,
  type SessionBriefJob,
} from "./session-brief-repository.js";

const RETENTION_MS = 24 * 60 * 60 * 1_000;

export class SessionBriefNotFoundError extends Error {}
export class SessionBriefNotSelectedError extends Error {}
export class SessionBriefObserverUnavailableError extends Error {}

export interface SessionBriefServiceOptions {
  repository: SessionBriefRepository;
  observer: Pick<ObserverService, "snapshot" | "on" | "off">;
  analyzer: SessionBriefAnalyzer;
  clock?: () => Date;
  retentionIntervalMs?: number;
  setInterval?: typeof setInterval;
  clearInterval?: typeof clearInterval;
  concurrency?: number;
}

interface SelectedRevision {
  threadId: string;
  updatedAt: string;
}

export class SessionBriefService extends EventEmitter {
  private readonly repository: SessionBriefRepository;
  private readonly observer: Pick<ObserverService, "snapshot" | "on" | "off">;
  private readonly analyzer: SessionBriefAnalyzer;
  private readonly clock: () => Date;
  private readonly retentionIntervalMs: number;
  private readonly setIntervalFn: typeof setInterval;
  private readonly clearIntervalFn: typeof clearInterval;
  private readonly concurrency: number;
  private readonly running = new Set<Promise<void>>();
  private selected: SelectedRevision[] = [];
  private selectedAt: string;
  private eventSequence = 0;
  private started = false;
  private acceptingWork = false;
  private retentionTimer: ReturnType<typeof setInterval> | null = null;

  private readonly observerListener = (event: { snapshot: ObserverSnapshot }) => {
    this.reconcile(event.snapshot);
  };

  constructor(options: SessionBriefServiceOptions) {
    super();
    this.repository = options.repository;
    this.observer = options.observer;
    this.analyzer = options.analyzer;
    this.clock = options.clock ?? (() => new Date());
    this.retentionIntervalMs = options.retentionIntervalMs ?? 60 * 60 * 1_000;
    this.setIntervalFn = options.setInterval ?? setInterval;
    this.clearIntervalFn = options.clearInterval ?? clearInterval;
    this.concurrency = Math.max(1, Math.min(options.concurrency ?? 1, 10));
    this.selectedAt = this.clock().toISOString();
  }

  start(): void {
    if (this.started) return;
    this.started = true;
    this.acceptingWork = true;
    const now = this.clock().toISOString();
    this.repository.recoverAnalyzing(now);
    this.repository.prune(this.expiryCutoff());
    this.observer.on("snapshot", this.observerListener);
    this.retentionTimer = this.setIntervalFn(() => {
      if (!this.started || !this.acceptingWork) return;
      if (this.repository.prune(this.expiryCutoff())) this.publish();
    }, this.retentionIntervalMs);
    this.reconcile(this.observer.snapshot());
  }

  async stop(): Promise<void> {
    if (!this.started) return;
    this.started = false;
    this.acceptingWork = false;
    this.observer.off("snapshot", this.observerListener);
    if (this.retentionTimer) this.clearIntervalFn(this.retentionTimer);
    this.retentionTimer = null;
    await this.drain();
  }

  async pauseAndDrain(): Promise<void> {
    this.acceptingWork = false;
    await this.drain();
  }

  resume(): void {
    if (!this.started) return;
    this.acceptingWork = true;
    this.reconcile(this.observer.snapshot());
  }

  snapshot(): SessionBriefSnapshot {
    const observerSnapshot = this.observer.snapshot();
    const items = this.selected.map((selected) =>
      this.itemForSnapshot(
        this.repository.item(
          selected.threadId,
          selected.updatedAt,
          this.selectedAt,
        ),
        observerSnapshot,
      ),
    );
    return {
      observer: {
        state: observerSnapshot.health.state,
        capability: observerSnapshot.health.capability,
      },
      selectedAt: this.selectedAt,
      items,
      total: items.length,
      queued: count(items, "queued"),
      analyzing: count(items, "analyzing"),
      ready: count(items, "ready"),
      stale: items.filter((item) => item.freshness === "stale").length,
      unavailable: count(items, "unavailable"),
      failed: count(items, "failed"),
    };
  }

  nextEvent(): SessionBriefSseEvent {
    return { id: String(++this.eventSequence), snapshot: this.snapshot() };
  }

  refreshAll(): SessionBriefSnapshot {
    this.assertObserverAvailable();
    const now = this.clock().toISOString();
    for (const selected of this.selected) {
      this.repository.enqueue(
        selected.threadId,
        selected.updatedAt,
        "manual",
        now,
        true,
      );
    }
    this.publish();
    this.pump();
    return this.snapshot();
  }

  refresh(threadId: string): SessionBriefSnapshot {
    this.assertObserverAvailable();
    const known = this.observer.snapshot().threads.some((thread) => thread.id === threadId);
    if (!known) {
      throw new SessionBriefNotFoundError("The observed session was not found.");
    }
    const selected = this.selected.find((item) => item.threadId === threadId);
    if (!selected) {
      throw new SessionBriefNotSelectedError(
        "The observed session is not in the current recent-session window.",
      );
    }
    this.repository.enqueue(
      selected.threadId,
      selected.updatedAt,
      "manual",
      this.clock().toISOString(),
      true,
    );
    this.publish();
    this.pump();
    return this.snapshot();
  }

  private reconcile(snapshot: ObserverSnapshot): void {
    if (!this.started) return;
    const now = this.clock().toISOString();
    this.selected = selectRecentSessions(snapshot.threads).map((thread) => ({
      threadId: thread.id,
      updatedAt: thread.updatedAt,
    }));
    this.selectedAt = now;
    this.repository.reconcileWindow(
      this.selected.map((item) => item.threadId),
      now,
      this.expiryCutoff(),
    );
    if (snapshot.health.state === "connected" && this.acceptingWork) {
      for (const selected of this.selected) {
        const item = this.repository.item(
          selected.threadId,
          selected.updatedAt,
          now,
        );
        if (item.freshness !== "current") {
          const retryUnavailable =
            item.analysisStatus === "unavailable" &&
            item.failure?.category === "observer_unavailable";
          this.repository.enqueue(
            selected.threadId,
            selected.updatedAt,
            retryUnavailable ? "retry" : "automatic",
            now,
            retryUnavailable,
          );
        }
      }
    } else {
      for (const selected of this.selected) {
        const job = this.repository.findJob(selected.threadId);
        if (job?.status === "queued") {
          this.repository.markFailure(
            job.jobId,
            "observer_unavailable",
            now,
            "unavailable",
          );
        }
      }
    }
    this.publish();
    this.pump();
  }

  private pump(): void {
    if (
      !this.started ||
      !this.acceptingWork ||
      this.observer.snapshot().health.state !== "connected"
    ) {
      return;
    }
    while (this.running.size < this.concurrency) {
      const queued = this.repository.nextQueued();
      if (!queued) break;
      const marked = this.repository.markAnalyzing(
        queued.jobId,
        this.clock().toISOString(),
      );
      if (!marked) continue;
      const work = this.run(marked);
      this.running.add(work);
      work.finally(() => {
        this.running.delete(work);
        this.publish();
        this.pump();
      });
      this.publish();
    }
  }

  private async run(job: SessionBriefJob): Promise<void> {
    try {
      const result = await this.analyzer.analyze({
        threadId: job.threadId,
        sourceUpdatedAt: job.targetUpdatedAt,
      });
      this.repository.promote(
        job.jobId,
        job.threadId,
        job.targetUpdatedAt,
        result,
        this.clock().toISOString(),
      );
    } catch {
      this.repository.markFailure(
        job.jobId,
        "internal",
        this.clock().toISOString(),
      );
    }
  }

  private async drain(): Promise<void> {
    await Promise.allSettled([...this.running]);
  }

  private assertObserverAvailable(): void {
    if (this.observer.snapshot().health.state !== "connected") {
      throw new SessionBriefObserverUnavailableError(
        "Codex is unavailable; no session briefs were queued.",
      );
    }
  }

  private itemForSnapshot(
    item: SessionBriefItem,
    observerSnapshot: ObserverSnapshot,
  ): SessionBriefItem {
    if (
      observerSnapshot.health.state !== "connected" &&
      item.freshness !== "current" &&
      item.analysisStatus === "unavailable" &&
      !item.failure
    ) {
      return {
        ...item,
        failure: {
          category: "observer_unavailable",
          at: this.selectedAt,
        },
      };
    }
    return item;
  }

  private expiryCutoff(): string {
    return new Date(this.clock().getTime() - RETENTION_MS).toISOString();
  }

  private publish(): void {
    this.emit("snapshot", this.nextEvent());
  }
}

function count(
  items: SessionBriefItem[],
  status: SessionBriefItem["analysisStatus"],
): number {
  return items.filter((item) => item.analysisStatus === status).length;
}

export function selectRecentSessions(threads: ObservedThread[]): ObservedThread[] {
  return threads
    .filter((thread) => !thread.archived)
    .sort((left, right) => {
      const recency = (right.recencyAt ?? right.updatedAt).localeCompare(
        left.recencyAt ?? left.updatedAt,
      );
      return recency || left.id.localeCompare(right.id);
    })
    .slice(0, 10);
}
