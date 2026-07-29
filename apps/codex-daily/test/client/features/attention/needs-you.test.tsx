import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { AttentionSnapshot } from "../../../../src/shared/attention";
import type { ObserverSnapshot } from "../../../../src/shared/observer-types";
import { AttentionProvider } from "../../../../src/client/data/attention-context";
import { ObserverProvider } from "../../../../src/client/data/observer-context";
import { NeedsYou } from "../../../../src/client/features/attention/NeedsYou";

const observer: ObserverSnapshot = {
  health: {
    state: "connected",
    capability: "standalone_history",
    lastSuccessfulSyncAt: "2026-07-29T12:00:00.000Z",
    lastInventoryRefreshAt: "2026-07-29T12:00:00.000Z",
    diagnostic: null,
  },
  threads: [
    {
      id: "thread-one",
      sessionId: "session-one",
      title: "Observed chat",
      cwd: "/workspace",
      source: "cli",
      cliVersion: "0.146.0",
      createdAt: "2026-07-29T10:00:00.000Z",
      updatedAt: "2026-07-29T10:00:00.000Z",
      recencyAt: "2026-07-29T10:00:00.000Z",
      archived: false,
      lastObservedAt: "2026-07-29T12:00:00.000Z",
      runtime: "active",
      waitingOnApproval: false,
      waitingOnUserInput: false,
      lastActivityAt: "2026-07-29T10:00:00.000Z",
    },
  ],
  activities: [],
  taskLinks: [],
};

const item = {
  id: "attention:stale:thread-one:2026-07-29T10:00:00.000Z",
  sourceKey: "stale:thread-one:2026-07-29T10:00:00.000Z",
  threadId: "thread-one",
  turnId: null,
  itemId: null,
  kind: "possibly_stale" as const,
  certainty: "possible" as const,
  sourceOccurredAt: "2026-07-29T10:00:00.000Z",
  lastDerivedAt: "2026-07-29T12:00:00.000Z",
  sourceLabel: "Possibly stale · lower certainty",
  lifecycle: "open" as const,
  localActionAt: null,
};

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("NeedsYou", () => {
  it("labels standalone coverage and removes an acknowledged item using only the local route", async () => {
    let attention: AttentionSnapshot = {
      capability: "standalone_history",
      connectionState: "connected",
      liveRequestCoverage: "external_clients_unavailable",
      items: [item],
    };
    const requests: Array<{ url: string; method: string }> = [];
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        requests.push({ url, method: init?.method ?? "GET" });
        if (url === "/api/observer") return Promise.resolve(Response.json(observer));
        if (url === "/api/attention") return Promise.resolve(Response.json(attention));
        if (url.includes("/api/attention/") && url.endsWith("/acknowledge")) {
          attention = { ...attention, items: [] };
          return Promise.resolve(Response.json(attention));
        }
        return Promise.resolve(Response.json({}, { status: 404 }));
      }),
    );

    render(
      <MemoryRouter>
        <ObserverProvider>
          <AttentionProvider>
            <NeedsYou timezone="Europe/Berlin" />
          </AttentionProvider>
        </ObserverProvider>
      </MemoryRouter>,
    );

    expect(
      await screen.findByText(/Standalone history mode cannot see live approvals/),
    ).toBeVisible();
    const card = screen.getByRole("listitem");
    expect(within(card).getByText("Possible signal")).toBeVisible();
    const user = userEvent.setup();
    await user.click(within(card).getByRole("button", { name: "Acknowledge" }));
    expect(await screen.findByText("Nothing needs you right now")).toBeVisible();
    expect(requests.filter((request) => request.method !== "GET")).toEqual([
      expect.objectContaining({
        url: expect.stringMatching(/^\/api\/attention\/.+\/acknowledge$/),
        method: "POST",
      }),
    ]);
    expect(
      requests.some(({ url }) => /approve|answer|turn\/|steer|interrupt/.test(url)),
    ).toBe(false);
  });
});
