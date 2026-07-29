import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import type {
  ObservedActivity,
  ObservedThread,
  ThreadDetail,
} from "../../../src/shared/observer-types";
import { ThreadDetailPage } from "../../../src/client/pages/ThreadDetailPage";

const now = "2026-07-29T12:00:00.000Z";
const thread: ObservedThread = {
  id: "retained-thread",
  sessionId: "retained-session",
  title: "Retained offline work",
  cwd: "/workspace/retained",
  source: "cli",
  cliVersion: "0.146.0",
  createdAt: now,
  updatedAt: now,
  recencyAt: now,
  archived: false,
  lastObservedAt: now,
  runtime: "unknown",
  waitingOnApproval: false,
  waitingOnUserInput: false,
  lastActivityAt: now,
};
const activity: ObservedActivity = {
  sourceKey: "turn:retained-thread:turn-one:failed",
  threadId: thread.id,
  turnId: "turn-one",
  itemId: null,
  occurredAt: now,
  category: "turn",
  lifecycle: "failed",
  label: "Turn failed",
};
const detail: ThreadDetail = {
  thread,
  activities: [activity],
  transientHistory: {
    status: "unavailable",
    reason: "Codex is disconnected; full history is unavailable.",
  },
};

vi.mock("../../../src/client/data/observer-context", () => ({
  useObserver: () => ({
    snapshot: {
      health: {
        state: "disconnected",
        capability: "shared_live",
        lastSuccessfulSyncAt: now,
        lastInventoryRefreshAt: now,
        diagnostic: "Codex is unavailable.",
      },
      threads: [thread],
      activities: [activity],
      taskLinks: [],
    },
    loading: false,
    error: null,
  }),
}));

vi.mock("../../../src/client/api/observer-client", () => ({
  getThreadDetail: vi.fn(async () => detail),
}));

vi.mock("../../../src/client/api/attention-client", () => ({
  getThreadAttention: vi.fn(async () => []),
}));

afterEach(cleanup);

describe("thread detail", () => {
  it("shows retained facts while truthfully reporting unavailable transient history", async () => {
    render(
      <MemoryRouter initialEntries={["/threads/retained-thread"]}>
        <Routes>
          <Route path="/threads/:threadId" element={<ThreadDetailPage />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(
      await screen.findByRole("heading", { name: "Retained offline work" }),
    ).toBeVisible();
    expect(screen.getByText(/Turn failed/)).toBeVisible();
    expect(
      screen.getByText("Codex is disconnected; full history is unavailable."),
    ).toBeVisible();
    expect(screen.queryByText(/turns fetched/)).not.toBeInTheDocument();
  });
});
