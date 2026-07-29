import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { SessionBriefSnapshot } from "../../../src/shared/session-briefs";
import {
  SessionBriefProvider,
  useSessionBriefs,
} from "../../../src/client/data/session-briefs-context";

const initial: SessionBriefSnapshot = {
  observer: { state: "connected", capability: "standalone_history" },
  selectedAt: "2026-07-29T12:00:00.000Z",
  items: [],
  total: 0,
  queued: 0,
  analyzing: 0,
  ready: 0,
  stale: 0,
  unavailable: 0,
  failed: 0,
};

const updated: SessionBriefSnapshot = {
  ...initial,
  selectedAt: "2026-07-29T12:01:00.000Z",
  items: [{
    threadId: "thread-one",
    targetUpdatedAt: "2026-07-29T12:00:00.000Z",
    analysisStatus: "queued",
    freshness: "missing",
    lastGood: null,
    failure: null,
    queuedAt: "2026-07-29T12:01:00.000Z",
    startedAt: null,
    updatedAt: "2026-07-29T12:01:00.000Z",
  }],
  total: 1,
  queued: 1,
};

class FakeEventSource {
  static instances: FakeEventSource[] = [];
  listeners = new Map<string, (event: MessageEvent<string>) => void>();
  onerror: (() => void) | null = null;
  close = vi.fn();

  constructor(public readonly url: string) {
    FakeEventSource.instances.push(this);
  }

  addEventListener(name: string, listener: EventListenerOrEventListenerObject) {
    this.listeners.set(name, listener as (event: MessageEvent<string>) => void);
  }

  emit(name: string, value: SessionBriefSnapshot) {
    this.listeners.get(name)?.({
      data: JSON.stringify(value),
    } as MessageEvent<string>);
  }

  emitRaw(name: string, value: string) {
    this.listeners.get(name)?.({ data: value } as MessageEvent<string>);
  }
}

function Consumer() {
  const briefs = useSessionBriefs();
  return (
    <div>
      <span>{briefs.loading ? "loading" : `total:${briefs.snapshot?.total ?? -1}`}</span>
      <span>{briefs.loadError ?? "no-load-error"}</span>
      <span>{briefs.streamError ?? "no-stream-error"}</span>
      <span>{briefs.mutationError ?? "no-mutation-error"}</span>
      <button
        type="button"
        disabled={briefs.refreshingAll}
        onClick={() => void briefs.refreshAll()}
      >
        Refresh all
      </button>
      <button
        type="button"
        disabled={briefs.pendingThreadIds.has("thread-one")}
        onClick={() => void briefs.refreshThread("thread-one")}
      >
        Refresh one
      </button>
    </div>
  );
}

beforeEach(() => {
  FakeEventSource.instances = [];
  vi.stubGlobal("EventSource", FakeEventSource);
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/api/session-briefs") {
        return new Response(JSON.stringify(initial), { status: 200 });
      }
      if (
        url === "/api/session-briefs/refresh" ||
        url === "/api/session-briefs/thread-one/refresh"
      ) {
        return new Response(JSON.stringify(updated), { status: 202 });
      }
      return new Response("{}", { status: 404 });
    }),
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("SessionBriefProvider", () => {
  it("loads, follows SSE, refreshes, retains the last snapshot on error, and closes", async () => {
    const view = render(
      <SessionBriefProvider>
        <Consumer />
      </SessionBriefProvider>,
    );
    expect(await screen.findByText("total:0")).toBeVisible();
    const source = FakeEventSource.instances[0]!;
    expect(source.url).toBe("/api/session-briefs/events");

    source.emit("session-briefs", updated);
    expect(await screen.findByText("total:1")).toBeVisible();
    source.emitRaw("session-briefs", "{not-json");
    expect(
      await screen.findByText(
        "A live session-brief update could not be read; the last snapshot remains visible.",
      ),
    ).toBeVisible();
    expect(screen.getByText("total:1")).toBeVisible();
    source.emitRaw(
      "session-briefs",
      JSON.stringify({ ...updated, items: [{ raw: "must not enter state" }] }),
    );
    expect(screen.getByText("total:1")).toBeVisible();
    source.onerror?.();
    expect(
      await screen.findByText(
        "Live brief updates paused; the last snapshot remains visible.",
      ),
    ).toBeVisible();
    expect(screen.getByText("total:1")).toBeVisible();

    await userEvent.click(screen.getByRole("button", { name: "Refresh all" }));
    await userEvent.click(screen.getByRole("button", { name: "Refresh one" }));
    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith(
        "/api/session-briefs/thread-one/refresh",
        expect.objectContaining({ method: "POST" }),
      );
    });
    view.unmount();
    expect(source.close).toHaveBeenCalledOnce();
  });

  it("does not open SSE after an initial read failure", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(
          JSON.stringify({ error: { message: "Brief inventory unavailable." } }),
          { status: 503 },
        ),
      ),
    );
    render(
      <SessionBriefProvider>
        <Consumer />
      </SessionBriefProvider>,
    );
    expect(await screen.findByText("Brief inventory unavailable.")).toBeVisible();
    expect(FakeEventSource.instances).toHaveLength(0);
  });
});
