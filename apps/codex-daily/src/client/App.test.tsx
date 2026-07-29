import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { representativeDay } from "../server/representative-day";
import type { HealthResponse } from "../shared/dashboard";
import { App } from "./App";

const health: HealthResponse = {
  service: "codex-daily",
  status: "ok",
  mode: "representative",
  connection: "not-connected",
};

function jsonResponse(body: unknown, init: ResponseInit = {}) {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "content-type": "application/json" },
    ...init,
  });
}

function mockSuccessfulApi() {
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/api/health") return Promise.resolve(jsonResponse(health));
      if (url === "/api/day") return Promise.resolve(jsonResponse(representativeDay));
      return Promise.resolve(jsonResponse({ error: "Not found" }, { status: 404 }));
    }),
  );
}

function renderApp(initialEntry = "/") {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <App />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  mockSuccessfulApi();
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("daily dashboard", () => {
  it("renders the exact approved hierarchy from the API contract", async () => {
    renderApp();

    expect(await screen.findByRole("heading", { name: "Needs your attention" })).toBeVisible();
    const sectionContainer = screen.getByTestId("dashboard-sections");
    const orderedHeadings = Array.from(sectionContainer.querySelectorAll(":scope > section")).map(
      (section) => section.querySelector("h2")?.textContent,
    );

    expect(orderedHeadings).toEqual([
      "Needs your attention",
      "Today’s outcomes and progress",
      "Active Codex chats",
      "Recently completed work",
      "Evening-report preview",
    ]);
  });

  it("keeps attention signals separate from routine and completed activity", async () => {
    renderApp();

    const attention = await screen.findByRole("heading", { name: "Needs your attention" });
    const attentionSection = attention.closest("section");
    expect(attentionSection).not.toBeNull();
    const scoped = within(attentionSection!);

    expect(scoped.getByText("Approval requested")).toBeVisible();
    expect(scoped.getByText("Direct question")).toBeVisible();
    expect(scoped.getByText("Turn failed")).toBeVisible();
    expect(scoped.getByText("Turn interrupted")).toBeVisible();
    expect(scoped.getByText("Explicit blocker")).toBeVisible();
    expect(scoped.getByText("Possibly stale · lower certainty")).toBeVisible();
    expect(scoped.queryByText("Working")).not.toBeInTheDocument();
    expect(scoped.queryByText("Confirmed complete")).not.toBeInTheDocument();
  });

  it("distinguishes suggested completion from user-confirmed completion", async () => {
    renderApp();

    expect(await screen.findByText("Confirmed complete")).toBeVisible();
    expect(screen.getByText("Looks complete · needs your confirmation")).toBeVisible();
    expect(screen.getByText("Only you can confirm this outcome.")).toBeVisible();
    expect(screen.queryByRole("button", { name: /confirm/i })).not.toBeInTheDocument();
  });

  it("shows a useful error while preserving the shell when the day request fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        if (String(input) === "/api/health") return Promise.resolve(jsonResponse(health));
        return Promise.resolve(jsonResponse({ error: "Unavailable" }, { status: 503 }));
      }),
    );
    renderApp();

    expect(await screen.findByRole("alert")).toHaveTextContent("Today’s snapshot is unavailable");
    expect(screen.getByRole("navigation", { name: "Primary" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Try loading again" })).toBeVisible();
  });
});

describe("secondary navigation", () => {
  it("uses real links for reports, settings, thread detail, and returning Today", async () => {
    const user = userEvent.setup();
    renderApp();

    await screen.findByRole("heading", { name: "Needs your attention" });
    await user.click(screen.getByRole("link", { name: "Reports" }));
    expect(screen.getByRole("heading", { name: "Report history" })).toBeVisible();
    expect(screen.getByText("No saved reports yet")).toBeVisible();

    await user.click(screen.getByRole("link", { name: "Settings" }));
    expect(screen.getByRole("heading", { name: "Settings" })).toBeVisible();
    expect(screen.getByText("Metadata only")).toBeVisible();

    await user.click(screen.getByRole("link", { name: "Today" }));
    await user.click(screen.getByRole("link", { name: "Onboarding refresh" }));
    expect(screen.getByRole("heading", { name: "Onboarding refresh" })).toBeVisible();
    expect(screen.getByText(/Full chat transcripts are not retained/)).toBeVisible();

    await user.click(screen.getByRole("link", { name: /Back to Today/ }));
    await waitFor(() =>
      expect(screen.getByRole("heading", { name: "Needs your attention" })).toBeVisible(),
    );
  });
});
