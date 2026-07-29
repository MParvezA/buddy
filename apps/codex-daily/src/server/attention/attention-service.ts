import { EventEmitter } from "node:events";
import type {
  AttentionLifecycle,
  AttentionSnapshot,
} from "../../shared/attention.js";
import type { ObserverSseEvent } from "../../shared/observer-types.js";
import { ObserverService } from "../codex/observer-service.js";
import { AttentionEngine } from "./attention-engine.js";
import { AttentionRepository } from "./attention-repository.js";
import { StalenessMonitor } from "./staleness-monitor.js";

export interface AttentionServiceOptions {
  repository: AttentionRepository;
  observer: ObserverService;
  clock?: () => Date;
  sweepIntervalMs?: number;
  setTimer?: typeof setTimeout;
  clearTimer?: typeof clearTimeout;
}

export class AttentionService extends EventEmitter {
  private readonly repository: AttentionRepository;
  private readonly observer: ObserverService;
  private readonly clock: () => Date;
  private readonly engine: AttentionEngine;
  private readonly monitor: StalenessMonitor;
  private readonly observerListener: (event: ObserverSseEvent) => void;
  private started = false;
  private eventSequence = 0;

  constructor(options: AttentionServiceOptions) {
    super();
    this.repository = options.repository;
    this.observer = options.observer;
    this.clock = options.clock ?? (() => new Date());
    this.engine = new AttentionEngine(this.repository, this.clock);
    this.monitor = new StalenessMonitor({
      sweep: () => this.reconcile(),
      intervalMs: options.sweepIntervalMs,
      setTimer: options.setTimer,
      clearTimer: options.clearTimer,
    });
    this.observerListener = () => this.reconcile();
  }

  start(): void {
    if (this.started) return;
    this.started = true;
    this.observer.on("snapshot", this.observerListener);
    this.monitor.start();
  }

  stop(): void {
    if (!this.started) return;
    this.started = false;
    this.monitor.stop();
    this.observer.off("snapshot", this.observerListener);
  }

  snapshot(): AttentionSnapshot {
    const observer = this.observer.snapshot();
    return {
      capability: observer.health.capability,
      connectionState: observer.health.state,
      liveRequestCoverage:
        observer.health.capability === "shared_live"
          ? "available"
          : "external_clients_unavailable",
      items: this.repository.listOpen(),
    };
  }

  nextEvent(): { id: string; snapshot: AttentionSnapshot } {
    return {
      id: String(++this.eventSequence),
      snapshot: this.snapshot(),
    };
  }

  acknowledge(id: string): "updated" | "not_found" | "not_actionable" {
    return this.markLocal(id, "acknowledged");
  }

  dismiss(id: string): "updated" | "not_found" | "not_actionable" {
    return this.markLocal(id, "dismissed");
  }

  private markLocal(
    id: string,
    lifecycle: Extract<AttentionLifecycle, "acknowledged" | "dismissed">,
  ): "updated" | "not_found" | "not_actionable" {
    const result = this.repository.markLocal(
      id,
      lifecycle,
      this.clock().toISOString(),
    );
    if (result === "updated") this.publish();
    return result;
  }

  threadHistory(threadId: string) {
    return this.repository.listForThread(threadId);
  }

  private reconcile(): void {
    this.engine.reconcile(this.observer.snapshot());
    this.publish();
  }

  private publish(): void {
    this.emit("snapshot", this.nextEvent());
  }
}
