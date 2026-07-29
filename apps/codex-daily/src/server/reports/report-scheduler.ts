import type { ReportSchedulerState } from "../../shared/report.js";
import type { SchedulerOperationalDiagnostics } from "../../shared/operations.js";
import { localDateFor } from "../planning/local-date.js";
import { ReportRepository } from "./report-repository.js";
import { ReportService } from "./report-service.js";
import { instantForLocal, nextLocalDate } from "./report-time.js";

export interface ReportSchedulerOptions {
  service: ReportService;
  repository: ReportRepository;
  clock?: () => Date;
  setTimer?: typeof setTimeout;
  clearTimer?: typeof clearTimeout;
}

export class ReportScheduler {
  private readonly service: ReportService;
  private readonly repository: ReportRepository;
  private readonly clock: () => Date;
  private readonly setTimer: typeof setTimeout;
  private readonly clearTimer: typeof clearTimeout;
  private timer: ReturnType<typeof setTimeout> | null = null;
  private nextRun: Date;
  private lastFailure: string | null = null;
  private lastRunTrigger: "scheduled" | "missed_recovery" | null = null;
  private lastRunOutcome: "created" | "already_exists" | "failed" | null = null;
  private missedRunRecoveredAt: string | null = null;
  private readonly activeRuns = new Set<Promise<void>>();
  private running = false;

  constructor(options: ReportSchedulerOptions) {
    this.service = options.service;
    this.repository = options.repository;
    this.clock = options.clock ?? (() => new Date());
    this.setTimer = options.setTimer ?? setTimeout;
    this.clearTimer = options.clearTimer ?? clearTimeout;
    this.nextRun = this.computeNextRun();
  }

  async start(): Promise<void> {
    if (this.running) return;
    this.running = true;
    await this.recoverToday();
    if (this.running) this.reschedule();
  }

  stop(): void {
    this.running = false;
    if (this.timer) this.clearTimer(this.timer);
    this.timer = null;
  }

  async stopAndDrain(): Promise<void> {
    this.stop();
    await Promise.allSettled([...this.activeRuns]);
    await this.service.drainNarratives();
  }

  resume(): void {
    if (this.running) return;
    this.running = true;
    this.reschedule();
  }

  async preferencesChanged(): Promise<void> {
    this.stop();
    this.running = true;
    await this.recoverToday();
    if (this.running) this.reschedule();
  }

  state(): ReportSchedulerState {
    return {
      schedule: this.service.schedule(),
      nextRunAt: this.nextRun.toISOString(),
      lastAutomaticRunAt: this.repository.lastAutomaticRunAt(),
      lastFailure: this.lastFailure,
    };
  }

  operationalDiagnostics(): SchedulerOperationalDiagnostics {
    return {
      nextRunAt: this.nextRun.toISOString(),
      lastAutomaticRunAt: this.repository.lastAutomaticRunAt(),
      lastRunTrigger: this.lastRunTrigger,
      lastRunOutcome: this.lastRunOutcome,
      missedRunRecoveredAt: this.missedRunRecoveredAt,
      lastFailure: this.lastFailure,
    };
  }

  private async recoverToday(): Promise<void> {
    const schedule = this.service.schedule();
    const localDate = localDateFor(this.clock, schedule.timezone);
    const due = instantForLocal(localDate, schedule.time, schedule.timezone);
    if (
      this.clock().valueOf() >= due.valueOf() &&
      !this.repository.automaticExists(localDate)
    ) {
      await this.trackRun(localDate, "missed_recovery");
    }
  }

  private computeNextRun(): Date {
    const schedule = this.service.schedule();
    let localDate = localDateFor(this.clock, schedule.timezone);
    let due = instantForLocal(localDate, schedule.time, schedule.timezone);
    if (due.valueOf() <= this.clock().valueOf()) {
      localDate = nextLocalDate(localDate);
      due = instantForLocal(localDate, schedule.time, schedule.timezone);
    }
    return due;
  }

  private reschedule(): void {
    if (!this.running) return;
    this.nextRun = this.computeNextRun();
    const delay = Math.max(0, this.nextRun.valueOf() - this.clock().valueOf());
    this.timer = this.setTimer(() => {
      this.timer = null;
      if (!this.running) return;
      if (this.clock().valueOf() < this.nextRun.valueOf()) {
        this.reschedule();
        return;
      }
      const schedule = this.service.schedule();
      const localDate = localDateFor(this.clock, schedule.timezone);
      void this.trackRun(localDate, "scheduled").finally(() => {
        if (this.running) this.reschedule();
      });
    }, Math.min(delay, 2_147_483_647));
  }

  private trackRun(
    localDate: string,
    trigger: "scheduled" | "missed_recovery",
  ): Promise<void> {
    const running = this.run(localDate, trigger);
    this.activeRuns.add(running);
    void running.finally(() => this.activeRuns.delete(running));
    return running;
  }

  private async run(
    localDate: string,
    trigger: "scheduled" | "missed_recovery",
  ): Promise<void> {
    try {
      const snapshot = await this.service.generate(localDate, trigger, false);
      this.lastRunTrigger = trigger;
      this.lastRunOutcome = snapshot ? "created" : "already_exists";
      if (snapshot && trigger === "missed_recovery") {
        this.missedRunRecoveredAt = this.clock().toISOString();
      }
      this.lastFailure = null;
    } catch {
      this.lastRunTrigger = trigger;
      this.lastRunOutcome = "failed";
      this.lastFailure = "Automatic report generation failed.";
    }
  }
}
