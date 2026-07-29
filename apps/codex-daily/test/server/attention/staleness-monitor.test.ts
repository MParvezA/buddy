// @vitest-environment node
import { afterEach, describe, expect, it, vi } from "vitest";
import { StalenessMonitor } from "../../../src/server/attention/staleness-monitor.js";

afterEach(() => {
  vi.useRealTimers();
});

describe("StalenessMonitor", () => {
  it("sweeps immediately and on the injected cadence without real waits", () => {
    vi.useFakeTimers();
    const sweep = vi.fn();
    const monitor = new StalenessMonitor({ sweep, intervalMs: 10_000 });
    monitor.start();
    expect(sweep).toHaveBeenCalledTimes(1);
    vi.advanceTimersByTime(29_999);
    expect(sweep).toHaveBeenCalledTimes(3);
    vi.advanceTimersByTime(1);
    expect(sweep).toHaveBeenCalledTimes(4);
    monitor.stop();
    vi.advanceTimersByTime(30_000);
    expect(sweep).toHaveBeenCalledTimes(4);
  });
});
