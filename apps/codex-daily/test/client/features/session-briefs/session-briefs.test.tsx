import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "../../../../src/client/App";
import type { ObserverSnapshot } from "../../../../src/shared/observer-types";
import type {
  SessionBriefItem,
  SessionBriefSnapshot,
} from "../../../../src/shared/session-briefs";

const now = "2026-07-29T14:00:00.000Z";

function observedThread(index: number, runtime: "active" | "idle" = "idle") {
  const minute = String(60 - index).padStart(2, "0");
  return {
    id: `thread-${index}`,
    sessionId: `session-${index}`,
    title: `Session ${index}`,
    cwd: `/workspace/session-${index}`,
    source: index % 2 ? "cli" : "vscode",
    cliVersion: "0.146.0",
    createdAt: `2026-07-29T12:${minute}:00.000Z`,
    updatedAt: `2026-07-29T13:${minute}:00.000Z`,
    recencyAt: `2026-07-29T13:${minute}:00.000Z`,
    archived: false,
    lastObservedAt: now,
    runtime,
    waitingOnApproval: false,
    waitingOnUserInput: false,
    lastActivityAt: `2026-07-29T13:${minute}:00.000Z`,
  } as const;
}

function briefItem(
  index: number,
  overrides: Partial<SessionBriefItem> = {},
): SessionBriefItem {
  return {
    threadId: `thread-${index}`,
    targetUpdatedAt: `2026-07-29T13:${String(60 - index).padStart(2, "0")}:00.000Z`,
    analysisStatus: "ready",
    freshness: "current",
    lastGood: {
      sourceUpdatedAt: `2026-07-29T13:${String(60 - index).padStart(2, "0")}:00.000Z`,
      generatedAt: now,
      generator: "codex_app_server",
      modelId: "gpt-5.6-sol",
      currentState: `Session ${index} is preparing the release.`,
      done: index === 1 ? ["The chat reports that tests passed."] : [],
      operatorActions: index === 1 ? ["Review the release checklist."] : [],
      blockers: [],
      confidence: index === 1 ? "high" : "medium",
      evidence: ["user:first-intent"],
    },
    failure: null,
    queuedAt: null,
    startedAt: null,
    updatedAt: now,
    ...overrides,
  };
}

function snapshot(
  items: SessionBriefItem[],
  overrides: Partial<SessionBriefSnapshot> = {},
): SessionBriefSnapshot {
  return {
    observer: { state: "connected", capability: "standalone_history" },
    selectedAt: now,
    items,
    total: items.length,
    queued: items.filter((item) => item.analysisStatus === "queued").length,
    analyzing: items.filter((item) => item.analysisStatus === "analyzing").length,
    ready: items.filter((item) => item.analysisStatus === "ready").length,
    stale: items.filter((item) => item.freshness === "stale").length,
    unavailable: items.filter((item) => item.analysisStatus === "unavailable").length,
    failed: items.filter((item) => item.analysisStatus === "failed").length,
    ...overrides,
  };
}

const threads = [
  ...Array.from({ length: 10 }, (_, index) => observedThread(index + 1)),
  observedThread(11, "active"),
];

const observer: ObserverSnapshot = {
  health: {
    state: "connected",
    capability: "standalone_history",
    lastSuccessfulSyncAt: now,
    lastInventoryRefreshAt: now,
    diagnostic: null,
  },
  threads,
  activities: [],
  taskLinks: [],
};

const planning = {
  localDate: "2026-07-29",
  timezone: "Europe/Berlin",
  reviewRequired: false,
  tasks: [{
    id: "task-one",
    localDate: "2026-07-29",
    title: "Release monitor",
    clarification: null,
    position: 0,
    lifecycle: "open",
    originTaskId: null,
    createdAt: now,
    updatedAt: now,
    completedAt: null,
    closedAt: null,
  }],
  priorDay: { localDate: "2026-07-28", unresolvedTasks: [] },
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

  emit(name: string, value: unknown) {
    this.listeners.get(name)?.({
      data: typeof value === "string" ? value : JSON.stringify(value),
    } as MessageEvent<string>);
  }
}

function baseFetch(initial: SessionBriefSnapshot) {
  let currentObserver = observer;
  return vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url === "/api/observer") return Response.json(currentObserver);
    if (url === "/api/planning") return Response.json(planning);
    if (url === "/api/session-briefs") return Response.json(initial);
    if (url === "/api/session-briefs/refresh") {
      return Response.json(snapshot(initial.items.map((item) => ({
        ...item,
        analysisStatus: "queued" as const,
        freshness: item.lastGood ? "stale" as const : "missing" as const,
        queuedAt: now,
      }))), { status: 202 });
    }
    if (url.match(/^\/api\/session-briefs\/[^/]+\/refresh$/)) {
      return Response.json(initial, { status: 202 });
    }
    if (url.includes("/api/tasks/") && init?.method === "PUT") {
      const segments = url.split("/");
      currentObserver = {
        ...currentObserver,
        taskLinks: [{
          taskId: segments[3]!,
          threadId: segments[5]!,
          createdAt: now,
        }],
      };
      return Response.json(currentObserver);
    }
    if (url === "/api/attention") {
      return Response.json({
        capability: "standalone_history",
        connectionState: "connected",
        liveRequestCoverage: "unavailable",
        items: [],
      });
    }
    if (url === "/api/reports/latest") {
      return Response.json({
        snapshot: null,
        scheduler: {
          schedule: { time: "18:00", timezone: "Europe/Berlin", narrativeEnabled: false },
          nextRunAt: now,
          lastAutomaticRunAt: null,
          lastFailure: null,
        },
      });
    }
    return Response.json({ error: { message: "Not found" } }, { status: 404 });
  });
}

function renderDashboard(initial: SessionBriefSnapshot) {
  vi.stubGlobal("fetch", baseFetch(initial));
  render(
    <MemoryRouter>
      <App />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  FakeEventSource.instances = [];
  vi.stubGlobal("EventSource", FakeEventSource);
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("Recent session briefs", () => {
  it("preserves canonical order, factual controls, structured meaning, and the ten-card cap", async () => {
    const items = Array.from({ length: 10 }, (_, index) => briefItem(index + 1));
    renderDashboard(snapshot(items));

    const heading = await screen.findByRole("heading", { name: "Recent session briefs" });
    const section = heading.closest("section")!;
    const cards = Array.from(section.querySelectorAll(".session-brief-card"));
    expect(cards).toHaveLength(10);
    expect(cards.map((card) => within(card).getByRole("heading", { level: 3 }).textContent))
      .toEqual(Array.from({ length: 10 }, (_, index) => `Session ${index + 1}`));
    expect(within(section).queryByText("Session 11")).not.toBeInTheDocument();
    expect(within(section).getByText("10 recent")).toBeVisible();

    const first = cards[0]!;
    expect(within(first).getByText("cli")).toBeVisible();
    expect(within(first).getByText("/workspace/session-1")).toBeVisible();
    expect(within(first).getByText("Idle")).toBeVisible();
    expect(within(first).getByText("Unplanned work")).toBeVisible();
    expect(within(first).getByRole("combobox")).toBeVisible();
    expect(within(first).getByRole("heading", { name: "Going on" })).toBeVisible();
    expect(within(first).getByRole("heading", { name: "Chat-reported done" })).toBeVisible();
    expect(within(first).getByRole("heading", { name: "What you should do" })).toBeVisible();
    expect(within(first).getByRole("heading", { name: "Blockers" })).toBeVisible();
    expect(within(first).getByText("GPT-5.6 derived")).toBeVisible();
    expect(within(first).getByText("High confidence")).toBeVisible();
    expect(within(first).getByText("Current")).toBeVisible();
    expect(within(first).getByText("No blocker inferred")).toBeVisible();
    expect(screen.queryByText("Active and recent Codex chats")).not.toBeInTheDocument();
  });

  it("streams progress into stable cards and retains a stale last good result after failure", async () => {
    const initial = snapshot([
      briefItem(1, {
        analysisStatus: "queued",
        freshness: "stale",
        queuedAt: now,
      }),
      briefItem(2, {
        analysisStatus: "analyzing",
        freshness: "missing",
        lastGood: null,
        startedAt: now,
      }),
    ]);
    renderDashboard(initial);
    expect(await screen.findByText("1 analyzing · 1 queued · 1 stale")).toBeVisible();
    expect(screen.getByText("Session 1 is preparing the release.")).toBeVisible();
    expect(screen.getByText("Stale")).toBeVisible();
    expect(screen.getByText("GPT-5.6 analysis in progress")).toBeVisible();

    const source = FakeEventSource.instances.find(
      (candidate) => candidate.url === "/api/session-briefs/events",
    )!;
    source.emit("session-briefs", snapshot([
      briefItem(1, {
        analysisStatus: "failed",
        freshness: "stale",
        failure: { category: "timeout", at: now },
      }),
      briefItem(2),
    ]));

    expect(await screen.findByText("1 ready · 1 failed · 1 stale")).toBeVisible();
    expect(screen.getByText("Session 1 is preparing the release.")).toBeVisible();
    expect(screen.getByText("GPT-5.6 analysis timed out.")).toBeVisible();
    expect(screen.getByRole("button", { name: "Retry brief for Session 1" })).toBeEnabled();
  });

  it("keeps refresh focus, prevents duplicate client requests, retries one card, and updates links", async () => {
    const failed = snapshot([
      briefItem(1, {
        analysisStatus: "failed",
        freshness: "missing",
        lastGood: null,
        failure: { category: "invalid_output", at: now },
      }),
    ]);
    const fetchMock = baseFetch(failed);
    vi.stubGlobal("fetch", fetchMock);
    render(
      <MemoryRouter>
        <App />
      </MemoryRouter>,
    );
    const user = userEvent.setup();
    const refresh = await screen.findByRole("button", { name: "Refresh 10 briefs" });
    refresh.focus();
    await user.keyboard("{Enter}");
    await waitFor(() => expect(refresh).toHaveFocus());
    expect(fetchMock.mock.calls.filter(([url]) => String(url) === "/api/session-briefs/refresh"))
      .toHaveLength(1);

    FakeEventSource.instances
      .find((candidate) => candidate.url === "/api/session-briefs/events")!
      .emit("session-briefs", failed);
    const retry = await screen.findByRole("button", {
      name: "Retry brief for Session 1",
    });
    await user.click(retry);
    expect(fetchMock.mock.calls.filter(([url]) =>
      String(url) === "/api/session-briefs/thread-1/refresh")).toHaveLength(1);

    await user.selectOptions(screen.getByRole("combobox"), "task-one");
    await user.click(screen.getByRole("button", { name: "Link" }));
    expect(await screen.findAllByText("Release monitor")).toHaveLength(2);
    expect(screen.queryByText("Unplanned work")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Session 1" })).toHaveAttribute(
      "href",
      "/threads/thread-1",
    );
  });

  it("keeps last-known facts visible when offline and explains disabled retry", async () => {
    const offline = snapshot([
      briefItem(1, {
        analysisStatus: "unavailable",
        freshness: "stale",
        failure: { category: "observer_unavailable", at: now },
      }),
    ], {
      observer: { state: "disconnected", capability: "standalone_history" },
    });
    renderDashboard(offline);
    expect(await screen.findByText("Session 1 is preparing the release.")).toBeVisible();
    expect(screen.getByText(/Brief refresh is unavailable while Codex is disconnected/))
      .toBeVisible();
    expect(screen.getByRole("button", { name: "Refresh 10 briefs" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Retry brief for Session 1" })).toBeDisabled();
    expect(screen.getByText("Retry is unavailable while Codex is disconnected."))
      .toBeVisible();
  });

  it("distinguishes no eligible sessions from a safe initial read failure", async () => {
    renderDashboard(snapshot([]));
    expect(await screen.findByRole("heading", { name: "No eligible Codex sessions" }))
      .toBeVisible();
    expect(screen.getByText("0 available")).toBeVisible();

    cleanup();
    const fetchMock = baseFetch(snapshot([]));
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        if (String(input) === "/api/session-briefs") {
          return Response.json(
            { error: { message: "Brief inventory unavailable." } },
            { status: 503 },
          );
        }
        return fetchMock(input, init);
      }),
    );
    render(
      <MemoryRouter>
        <App />
      </MemoryRouter>,
    );
    expect(await screen.findByText(/Brief inventory unavailable/)).toBeVisible();
    expect(screen.getByRole("heading", { name: "Today’s outcomes and progress" }))
      .toBeVisible();
    expect(screen.queryByRole("heading", { name: "No eligible Codex sessions" }))
      .not.toBeInTheDocument();
  });

  it("shows a safe mutation failure without erasing the last good brief", async () => {
    const ready = snapshot([briefItem(1)]);
    const fetchMock = baseFetch(ready);
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        if (String(input) === "/api/session-briefs/refresh") {
          return Response.json(
            { error: { message: "Brief refresh is temporarily unavailable." } },
            { status: 503 },
          );
        }
        return fetchMock(input, init);
      }),
    );
    render(
      <MemoryRouter>
        <App />
      </MemoryRouter>,
    );
    const user = userEvent.setup();
    expect(await screen.findByText("Session 1 is preparing the release.")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Refresh 10 briefs" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Brief refresh is temporarily unavailable.",
    );
    expect(screen.getByText("Session 1 is preparing the release.")).toBeVisible();
  });
});
