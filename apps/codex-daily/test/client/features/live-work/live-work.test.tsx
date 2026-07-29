import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "../../../../src/client/App";
import type { ObserverSnapshot } from "../../../../src/shared/observer-types";

const task = {
  id: "task-one",
  localDate: "2026-07-29",
  title: "Daily monitor",
  clarification: null,
  position: 0,
  lifecycle: "open" as const,
  originTaskId: null,
  createdAt: "2026-07-29T08:00:00.000Z",
  updatedAt: "2026-07-29T08:00:00.000Z",
  completedAt: null,
  closedAt: null,
};
const snapshot: ObserverSnapshot = {
  health: {
    state: "connected",
    capability: "standalone_history",
    lastSuccessfulSyncAt: "2026-07-29T12:00:00.000Z",
    lastInventoryRefreshAt: "2026-07-29T12:00:00.000Z",
    diagnostic: "History polling is connected; live requests may not be visible.",
  },
  threads: [
    {
      id: "thread-one",
      sessionId: "session-one",
      title: "Observed chat",
      cwd: "/workspace",
      source: "cli",
      cliVersion: "0.146.0",
      createdAt: "2026-07-29T08:00:00.000Z",
      updatedAt: "2026-07-29T12:00:00.000Z",
      recencyAt: "2026-07-29T12:00:00.000Z",
      archived: false,
      lastObservedAt: "2026-07-29T12:00:00.000Z",
      runtime: "active",
      waitingOnApproval: false,
      waitingOnUserInput: false,
      lastActivityAt: "2026-07-29T12:00:00.000Z",
    },
  ],
  activities: [
    {
      sourceKey: "turn:one:completed",
      threadId: "thread-one",
      turnId: "turn-one",
      itemId: null,
      occurredAt: "2026-07-29T12:00:00.000Z",
      category: "turn",
      lifecycle: "completed",
      label: "Turn completed",
    },
  ],
  taskLinks: [],
};

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("Live Work", () => {
  it("shows capability-aware observed state and creates an explicit local task link", async () => {
    let current = snapshot;
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url === "/api/planning") {
          return Promise.resolve(
            Response.json({
              localDate: "2026-07-29",
              timezone: "Europe/Berlin",
              reviewRequired: false,
              tasks: [task],
              priorDay: { localDate: "2026-07-28", unresolvedTasks: [] },
            }),
          );
        }
        if (url === "/api/observer") return Promise.resolve(Response.json(current));
        if (url.includes("/api/tasks/") && init?.method === "PUT") {
          current = {
            ...current,
            taskLinks: [
              {
                taskId: task.id,
                threadId: "thread-one",
                createdAt: "2026-07-29T12:01:00.000Z",
              },
            ],
          };
          return Promise.resolve(Response.json(current));
        }
        return Promise.resolve(Response.json({}));
      }),
    );

    render(
      <MemoryRouter>
        <App />
      </MemoryRouter>,
    );
    expect((await screen.findAllByRole("link", { name: "Observed chat" }))[0]).toBeVisible();
    expect(screen.getByText("Unplanned work")).toBeVisible();
    expect(screen.getByText(/History polling is connected/)).toBeVisible();
    const user = userEvent.setup();
    await user.selectOptions(screen.getByRole("combobox"), task.id);
    await user.click(screen.getByRole("button", { name: "Link" }));
    await waitFor(() => expect(screen.getAllByText("Daily monitor")).toHaveLength(2));
    expect(screen.queryByText("Unplanned work")).not.toBeInTheDocument();
  });
});
