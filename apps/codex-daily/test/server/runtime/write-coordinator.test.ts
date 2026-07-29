// @vitest-environment node
import { describe, expect, it } from "vitest";
import {
  LocalDataBusyError,
  WriteCoordinator,
} from "../../../src/server/runtime/write-coordinator.js";

describe("WriteCoordinator", () => {
  it("drains active writes and rejects new writes during exclusive maintenance", async () => {
    const coordinator = new WriteCoordinator();
    const release = coordinator.beginWrite();
    const events: string[] = [];
    const operation = coordinator.exclusive(
      async () => events.push("paused"),
      async () => events.push("deleted"),
      async () => events.push("resumed"),
    );
    await Promise.resolve();
    expect(() => coordinator.beginWrite()).toThrow(LocalDataBusyError);
    expect(events).toEqual([]);
    release();
    await operation;
    expect(events).toEqual(["paused", "deleted", "resumed"]);
    coordinator.beginWrite()();
  });
});
