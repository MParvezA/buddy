export interface StalenessMonitorOptions {
  sweep: () => void;
  intervalMs?: number;
  setTimer?: typeof setTimeout;
  clearTimer?: typeof clearTimeout;
}

export class StalenessMonitor {
  private readonly intervalMs: number;
  private readonly setTimer: typeof setTimeout;
  private readonly clearTimer: typeof clearTimeout;
  private timer: ReturnType<typeof setTimeout> | null = null;
  private running = false;

  constructor(private readonly options: StalenessMonitorOptions) {
    this.intervalMs = options.intervalMs ?? 60_000;
    this.setTimer = options.setTimer ?? setTimeout;
    this.clearTimer = options.clearTimer ?? clearTimeout;
  }

  start(): void {
    if (this.running) return;
    this.running = true;
    this.options.sweep();
    this.schedule();
  }

  stop(): void {
    this.running = false;
    if (this.timer) this.clearTimer(this.timer);
    this.timer = null;
  }

  private schedule(): void {
    if (!this.running) return;
    this.timer = this.setTimer(() => {
      this.timer = null;
      if (!this.running) return;
      this.options.sweep();
      this.schedule();
    }, this.intervalMs);
  }
}
