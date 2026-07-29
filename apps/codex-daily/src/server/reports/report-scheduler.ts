import type { ReportSchedulerState } from "../../shared/report.js";
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

  constructor(options: ReportSchedulerOptions) {
    this.service = options.service;
    this.repository = options.repository;
    this.clock = options.clock ?? (() => new Date());
    this.setTimer = options.setTimer ?? setTimeout;
    this.clearTimer = options.clearTimer ?? clearTimeout;
    this.nextRun = this.computeNextRun();
  }

  async start(): Promise<void> {
    await this.recoverToday();
    this.reschedule();
  }

  stop(): void {
    if (this.timer) this.clearTimer(this.timer);
    this.timer = null;
  }

  async preferencesChanged(): Promise<void> {
    this.stop();
    await this.recoverToday();
    this.reschedule();
  }

  state(): ReportSchedulerState {
    return {
      schedule: this.service.schedule(),
      nextRunAt: this.nextRun.toISOString(),
      lastAutomaticRunAt: this.repository.lastAutomaticRunAt(),
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
      await this.run(localDate, "missed_recovery");
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
    this.nextRun = this.computeNextRun();
    const delay = Math.max(0, this.nextRun.valueOf() - this.clock().valueOf());
    this.timer = this.setTimer(() => {
      const schedule = this.service.schedule();
      const localDate = localDateFor(this.clock, schedule.timezone);
      void this.run(localDate, "scheduled").finally(() => this.reschedule());
    }, Math.min(delay, 2_147_483_647));
  }

  private async run(
    localDate: string,
    trigger: "scheduled" | "missed_recovery",
  ): Promise<void> {
    try {
      await this.service.generate(localDate, trigger);
      this.lastFailure = null;
    } catch {
      this.lastFailure = "Automatic report generation failed.";
    }
  }
}
