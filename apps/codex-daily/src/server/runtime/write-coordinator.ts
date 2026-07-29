export class LocalDataBusyError extends Error {}

export class WriteCoordinator {
  private acceptingWrites = true;
  private activeWrites = 0;
  private readonly drainWaiters = new Set<() => void>();
  private exclusiveTail: Promise<void> = Promise.resolve();

  beginWrite(): () => void {
    if (!this.acceptingWrites) {
      throw new LocalDataBusyError("Local data maintenance is in progress.");
    }
    this.activeWrites += 1;
    let released = false;
    return () => {
      if (released) return;
      released = true;
      this.activeWrites -= 1;
      if (this.activeWrites === 0) {
        for (const resolve of this.drainWaiters) resolve();
        this.drainWaiters.clear();
      }
    };
  }

  async exclusive<T>(
    pauseWriters: () => Promise<void>,
    work: () => T | Promise<T>,
    resumeWriters: () => Promise<void>,
  ): Promise<T> {
    const previous = this.exclusiveTail;
    let releaseExclusive = () => {};
    this.exclusiveTail = new Promise<void>((resolve) => {
      releaseExclusive = resolve;
    });
    await previous;
    this.acceptingWrites = false;
    try {
      await this.waitForWrites();
      await pauseWriters();
      return await work();
    } finally {
      try {
        await resumeWriters();
      } finally {
        this.acceptingWrites = true;
        releaseExclusive();
      }
    }
  }

  private async waitForWrites(): Promise<void> {
    if (this.activeWrites === 0) return;
    await new Promise<void>((resolve) => this.drainWaiters.add(resolve));
  }
}
