import { EventEmitter } from "node:events";
import type {
  ObservedThread,
  ObserverSnapshot,
} from "../../shared/observer-types.js";
import type {
  SessionBriefFailureCategory,
  SessionBriefItem,
  SessionBriefSnapshot,
  SessionBriefSseEvent,
} from "../../shared/session-briefs.js";
import type { SessionBriefOperationalDiagnostics } from "../../shared/operations.js";
import type { ObserverService } from "../codex/observer-service.js";
import {
  SessionBriefAnalysisError,
  type SessionBriefAnalyzer,
} from "./session-brief-analyzer.js";
import {
  SessionBriefRepository,
  type SessionBriefJob,
} from "./session-brief-repository.js";

const RETENTION_MS = 24 * 60 * 60 * 1_000;
const DEFAULT_DEBOUNCE_MS = 30_000;
const DEFAULT_RETRY_DELAYS_MS = [30_000, 120_000] as const;

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
  setTimer?: typeof setTimeout;
  clearTimer?: typeof clearTimeout;
  debounceMs?: number;
  retryDelaysMs?: readonly [number, number];
  concurrency?: number;
}

interface SelectedRevision {
  threadId: string;
  updatedAt: string;
}

interface RunningWork {
  promise: Promise<void>;
  controller: AbortController;
}

export class SessionBriefService extends EventEmitter {
  private readonly repository: SessionBriefRepository;
  private readonly observer: Pick<ObserverService, "snapshot" | "on" | "off">;
  private readonly analyzer: SessionBriefAnalyzer;
  private readonly clock: () => Date;
  private readonly retentionIntervalMs: number;
  private readonly setIntervalFn: typeof setInterval;
  private readonly clearIntervalFn: typeof clearInterval;
  private readonly setTimer: typeof setTimeout;
  private readonly clearTimer: typeof clearTimeout;
  private readonly debounceMs: number;
  private readonly retryDelaysMs: readonly [number, number];
  private readonly concurrency: number;
  private readonly running = new Map<string, RunningWork>();
  private selected: SelectedRevision[] = [];
  private selectedAt: string;
  private eventSequence = 0;
  private started = false;
  private acceptingWork = false;
  private epoch = 0;
  private retentionTimer: ReturnType<typeof setInterval> | null = null;
  private dueTimer: ReturnType<typeof setTimeout> | null = null;
  private observedPeakConcurrency = 0;
  private lastPruneAt: string | null = null;
  private lastPrunedRowCount = 0;
  private orphanJobsRecoveredAtStartup = 0;
  private shutdownState: SessionBriefOperationalDiagnostics["shutdownState"] = "stopped";

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
    this.setTimer = options.setTimer ?? setTimeout;
    this.clearTimer = options.clearTimer ?? clearTimeout;
    this.debounceMs = options.debounceMs ?? DEFAULT_DEBOUNCE_MS;
    this.retryDelaysMs = options.retryDelaysMs ?? DEFAULT_RETRY_DELAYS_MS;
    this.concurrency = Math.max(1, Math.min(options.concurrency ?? 2, 2));
    this.selectedAt = this.clock().toISOString();
  }

  start(): void {
    if (this.started) return;
    this.started = true;
    this.acceptingWork = true;
    this.shutdownState = "running";
    this.epoch = this.repository.advanceCoordinatorEpoch();
    const now = this.clock().toISOString();
    this.orphanJobsRecoveredAtStartup = this.repository.recoverAnalyzing(now);
    this.recordPrune(this.repository.prune(this.expiryCutoff()), now);
    this.observer.on("snapshot", this.observerListener);
    this.retentionTimer = this.setIntervalFn(() => {
      if (!this.started || !this.acceptingWork) return;
      const pruneNow = this.clock().toISOString();
      const pruned = this.repository.prune(this.expiryCutoff());
      this.recordPrune(pruned, pruneNow);
      if (pruned) this.publish();
    }, this.retentionIntervalMs);
    this.reconcile(this.observer.snapshot());
  }

  async stop(): Promise<void> {
    if (!this.started) return;
    this.started = false;
    this.observer.off("snapshot", this.observerListener);
    if (this.retentionTimer) this.clearIntervalFn(this.retentionTimer);
    this.retentionTimer = null;
    await this.pauseAndDrain();
  }

  async pauseAndDrain(): Promise<void> {
    this.acceptingWork = false;
    this.shutdownState = "draining";
    this.epoch = this.repository.advanceCoordinatorEpoch();
    this.clearDueTimer();
    for (const work of this.running.values()) work.controller.abort();
    await Promise.allSettled([...this.running.values()].map((work) => work.promise));
    this.shutdownState = this.started ? "paused" : "stopped";
  }

  resume(): void {
    if (!this.started) return;
    this.acceptingWork = true;
    this.shutdownState = "running";
    this.epoch = this.repository.advanceCoordinatorEpoch();
    this.repository.recoverAnalyzing(this.clock().toISOString());
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

  operationalDiagnostics(): SessionBriefOperationalDiagnostics {
    const snapshot = this.snapshot();
    const selectedIds = new Set(this.selected.map((item) => item.threadId));
    const jobs = this.repository
      .listJobsForExport()
      .filter((job) => selectedIds.has(job.threadId));
    const successful = this.repository
      .listBriefRowsForExport()
      .sort((left, right) =>
        right.lastGood.generatedAt.localeCompare(left.lastGood.generatedAt)
      )[0]?.lastGood ?? null;
    const lastFailure = jobs
      .filter((job) => job.failureAt && job.failureCategory)
      .sort((left, right) =>
        (right.failureAt ?? "").localeCompare(left.failureAt ?? "")
      )[0] ?? null;
    const retryWaiting = jobs.filter(
      (job) => job.status === "queued" && job.reason === "retry",
    ).length;
    const queuedJobs = jobs.filter((job) => job.status === "queued").length;
    return {
      selectedRecentSessions: snapshot.total,
      queued: Math.max(0, queuedJobs - retryWaiting),
      retryWaiting,
      analyzing: jobs.filter((job) => job.status === "analyzing").length,
      readyCurrent: snapshot.items.filter(
        (item) =>
          item.analysisStatus === "ready" && item.freshness === "current",
      ).length,
      stale: snapshot.stale,
      unavailable: snapshot.unavailable,
      failed: snapshot.failed,
      configuredWorkerConcurrency: this.concurrency,
      activeWorkerCount: this.running.size,
      observedPeakWorkerConcurrency: this.observedPeakConcurrency,
      lastSuccessfulGenerationAt: successful?.generatedAt ?? null,
      lastSuccessfulModelId: successful?.modelId ?? null,
      lastFailureCategory: lastFailure?.failureCategory ?? null,
      lastFailureAt: lastFailure?.failureAt ?? null,
      retainedRetryCount: jobs.reduce(
        (total, job) => total + Math.max(0, job.attemptCount - 1),
        0,
      ),
      lastPruneAt: this.lastPruneAt,
      lastPrunedRowCount: this.lastPrunedRowCount,
      orphanJobsRecoveredAtStartup: this.orphanJobsRecoveredAtStartup,
      shutdownState: this.shutdownState,
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
    const nowDate = this.clock();
    const now = nowDate.toISOString();
    this.selected = selectRecentSessions(snapshot.threads).map((thread) => ({
      threadId: thread.id,
      updatedAt: thread.updatedAt,
    }));
    this.selectedAt = now;
    const pruned = this.repository.reconcileWindow(
      this.selected.map((item) => item.threadId),
      now,
      this.expiryCutoff(),
    );
    this.recordPrune(pruned, now);
    if (usableSnapshot(snapshot) && this.acceptingWork) {
      for (const selected of this.selected) {
        const item = this.repository.item(
          selected.threadId,
          selected.updatedAt,
          now,
        );
        const currentJob = this.repository.findJob(selected.threadId);
        const alreadyDesired =
          currentJob?.targetUpdatedAt === selected.updatedAt;
        if (
          item.freshness !== "current" &&
          !alreadyDesired
        ) {
          const dueAt = new Date(nowDate.getTime() + this.debounceMs).toISOString();
          this.repository.enqueue(
            selected.threadId,
            selected.updatedAt,
            "automatic",
            dueAt,
          );
        }
      }
    }
    this.publish();
    this.pump();
  }

  private pump(): void {
    this.clearDueTimer();
    if (
      !this.started ||
      !this.acceptingWork ||
      !usableSnapshot(this.observer.snapshot())
    ) {
      return;
    }
    while (this.running.size < this.concurrency) {
      const now = this.clock().toISOString();
      const queued = this.nextQueued(now);
      if (!queued) break;
      const marked = this.repository.markAnalyzing(queued.jobId, now);
      if (!marked) continue;
      const controller = new AbortController();
      const epoch = this.epoch;
      const promise = this.run(marked, controller.signal, epoch);
      this.running.set(marked.jobId, { promise, controller });
      this.observedPeakConcurrency = Math.max(
        this.observedPeakConcurrency,
        this.running.size,
      );
      void promise.finally(() => {
        this.running.delete(marked.jobId);
        this.publish();
        this.pump();
      });
      this.publish();
    }
    this.scheduleDuePump();
  }

  private async run(
    job: SessionBriefJob,
    signal: AbortSignal,
    epoch: number,
  ): Promise<void> {
    try {
      const result = await this.analyzer.analyze({
        threadId: job.threadId,
        sourceUpdatedAt: job.targetUpdatedAt,
        signal,
      });
      if (!this.isCurrentWork(job, epoch, signal)) return;
      this.repository.promote(
        job.jobId,
        job.threadId,
        job.targetUpdatedAt,
        result,
        this.clock().toISOString(),
        epoch,
      );
    } catch (error) {
      if (!this.isCurrentWork(job, epoch, signal)) return;
      const failure =
        error instanceof SessionBriefAnalysisError
          ? error
          : new SessionBriefAnalysisError("internal", false);
      const now = this.clock();
      if (failure.transient && job.attemptCount < 3) {
        const delay = this.retryDelaysMs[Math.max(0, job.attemptCount - 1)];
        this.repository.scheduleRetry(
          job.jobId,
          failure.category,
          now.toISOString(),
          new Date(now.getTime() + delay).toISOString(),
        );
      } else {
        this.repository.markFailure(
          job.jobId,
          failure.category,
          now.toISOString(),
          unavailableStatus(failure.category) ? "unavailable" : "failed",
        );
      }
    }
  }

  private isCurrentWork(
    job: SessionBriefJob,
    epoch: number,
    signal: AbortSignal,
  ): boolean {
    if (
      signal.aborted ||
      !this.started ||
      !this.acceptingWork ||
      epoch !== this.epoch
    ) {
      return false;
    }
    const selected = this.selected.find((item) => item.threadId === job.threadId);
    const current = this.repository.findJob(job.threadId);
    return Boolean(
      selected?.updatedAt === job.targetUpdatedAt &&
      current?.jobId === job.jobId &&
      current.status === "analyzing",
    );
  }

  private scheduleDuePump(): void {
    if (this.dueTimer || !this.started || !this.acceptingWork) return;
    const dueAt = this.repository.nextQueuedAt();
    if (!dueAt) return;
    const delay = Math.max(0, new Date(dueAt).getTime() - this.clock().getTime());
    this.dueTimer = this.setTimer(() => {
      this.dueTimer = null;
      this.pump();
    }, delay);
  }

  private nextQueued(now: string): SessionBriefJob | null {
    const recency = new Map(
      this.selected.map((item, index) => [item.threadId, index]),
    );
    return this.repository.listDueQueued(now).sort((left, right) => {
      const manual =
        Number(left.reason !== "manual") - Number(right.reason !== "manual");
      if (manual) return manual;
      const due = left.queuedAt.localeCompare(right.queuedAt);
      if (due) return due;
      const recent =
        (recency.get(left.threadId) ?? Number.MAX_SAFE_INTEGER) -
        (recency.get(right.threadId) ?? Number.MAX_SAFE_INTEGER);
      return recent || left.threadId.localeCompare(right.threadId);
    })[0] ?? null;
  }

  private clearDueTimer(): void {
    if (this.dueTimer) this.clearTimer(this.dueTimer);
    this.dueTimer = null;
  }

  private assertObserverAvailable(): void {
    if (!usableSnapshot(this.observer.snapshot()) || !this.acceptingWork) {
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
      !usableSnapshot(observerSnapshot) &&
      item.freshness !== "current" &&
      !item.failure
    ) {
      return {
        ...item,
        analysisStatus: "unavailable",
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

  private recordPrune(count: number, at: string): void {
    this.lastPruneAt = at;
    this.lastPrunedRowCount = count;
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

function unavailableStatus(category: SessionBriefFailureCategory): boolean {
  return ["observer_unavailable", "analysis_unavailable"].includes(category);
}

function usableSnapshot(snapshot: ObserverSnapshot): boolean {
  return (
    snapshot.health.state === "connected" &&
    snapshot.health.lastInventoryRefreshAt !== null
  );
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
