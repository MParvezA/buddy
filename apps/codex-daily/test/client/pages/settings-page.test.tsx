import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { OperationsDiagnostics } from "../../../src/shared/operations";
import { SettingsPage } from "../../../src/client/pages/SettingsPage";

const diagnostics: OperationsDiagnostics = {
  localOnly: true,
  dataLocation: "/local/codex-daily.sqlite",
  schedule: {
    time: "18:00",
    timezone: "Europe/Berlin",
    narrativeEnabled: false,
  },
  retainedCounts: [
    { category: "days", count: 1 },
    { category: "tasks", count: 2 },
  ],
  retainedDates: { oldest: "2026-07-29", newest: "2026-07-29" },
  database: {
    status: "ok",
    schemaVersion: "005_operational_hardening.sql",
    foreignKeyViolations: 0,
  },
  observer: {
    state: "connected",
    lastSuccessfulSyncAt: "2026-07-29T12:00:00.000Z",
    reconnectAttempt: 0,
    reconnectBackoffMs: null,
    lastErrorCategory: null,
    lastErrorAt: null,
    replayedEventCount: 3,
    ignoredEventCount: 1,
  },
  scheduler: {
    nextRunAt: "2026-07-29T16:00:00.000Z",
    lastAutomaticRunAt: null,
    lastRunTrigger: null,
    lastRunOutcome: null,
    missedRunRecoveredAt: null,
    lastFailure: null,
  },
  reports: {
    lastFactualReportAt: null,
    lastNarrativeOutcome: null,
  },
  runtime: {
    application: "codex-daily",
    version: "0.1.0",
    node: "v24.0.0",
  },
};

function response(body: unknown) {
  return Promise.resolve(
    new Response(JSON.stringify(body), {
      status: 200,
      headers: { "content-type": "application/json" },
    }),
  );
}

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL) => {
      if (String(input) === "/api/report-settings") {
        return response({
          schedule: diagnostics.schedule,
          nextRunAt: diagnostics.scheduler.nextRunAt,
          lastAutomaticRunAt: null,
          lastFailure: null,
        });
      }
      if (String(input) === "/api/operations/diagnostics") {
        return response(diagnostics);
      }
      return response({});
    }),
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("Settings local-data controls", () => {
  it("does not expose editable defaults while retained settings are still loading", () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        if (String(input) === "/api/report-settings") {
          return new Promise<Response>(() => undefined);
        }
        if (String(input) === "/api/operations/diagnostics") {
          return response(diagnostics);
        }
        return response({});
      }),
    );
    render(
      <MemoryRouter>
        <SettingsPage />
      </MemoryRouter>,
    );

    expect(screen.getByLabelText("Evening report time")).toBeDisabled();
    expect(screen.getByLabelText("Evening report time")).toHaveValue("");
    expect(screen.getByLabelText("IANA timezone")).toBeDisabled();
    expect(screen.getByLabelText("IANA timezone")).toHaveValue("");
    expect(screen.getByRole("button", { name: "Save report settings" })).toBeDisabled();
    expect(screen.getByText("Loading retained report settings…")).toBeVisible();
  });

  it("shows bounded diagnostics and restores focus after a keyboard-cancelled dialog", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <SettingsPage />
      </MemoryRouter>,
    );
    expect(await screen.findByText("005_operational_hardening.sql", { exact: false })).toBeVisible();
    expect(screen.getByText("3 replayed/deduplicated; 1 ignored")).toBeVisible();
    expect(screen.getByRole("link", { name: "Export JSON" })).toHaveAttribute(
      "href",
      "/api/operations/export",
    );

    const opener = screen.getByRole("button", { name: "Delete all local data" });
    await user.click(opener);
    const dialog = screen.getByRole("dialog", { name: "Delete all local data?" });
    const confirmation = screen.getByLabelText("Confirmation");
    expect(confirmation).toHaveFocus();
    await user.type(confirmation, "DELETE ALL CODEX DAILY DATA");
    await user.keyboard("{Shift>}{Tab}{/Shift}");
    expect(
      screen.getByRole("button", { name: "Delete local data" }),
    ).toHaveFocus();
    await user.keyboard("{Escape}");
    expect(dialog).not.toBeInTheDocument();
    await vi.waitFor(() => expect(opener).toHaveFocus());
  });

  it("keeps deletion failures inside the open confirmation dialog", async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
        if (String(input) === "/api/report-settings") {
          return response({
            schedule: diagnostics.schedule,
            nextRunAt: diagnostics.scheduler.nextRunAt,
            lastAutomaticRunAt: null,
            lastFailure: null,
          });
        }
        if (String(input) === "/api/operations/diagnostics") {
          return response(diagnostics);
        }
        if (
          String(input) === "/api/operations/data" &&
          init?.method === "DELETE"
        ) {
          return Promise.resolve(
            new Response(
              JSON.stringify({ error: { message: "Deletion could not finish." } }),
              {
                status: 500,
                headers: { "content-type": "application/json" },
              },
            ),
          );
        }
        return response({});
      }),
    );
    render(
      <MemoryRouter>
        <SettingsPage />
      </MemoryRouter>,
    );
    await screen.findByDisplayValue("Europe/Berlin");
    await user.click(screen.getByRole("button", { name: "Delete all local data" }));
    const dialog = screen.getByRole("dialog", { name: "Delete all local data?" });
    await user.type(
      screen.getByLabelText("Confirmation"),
      "DELETE ALL CODEX DAILY DATA",
    );
    await user.click(screen.getByRole("button", { name: "Delete local data" }));

    expect(within(dialog).getByRole("alert")).toHaveTextContent(
      "Deletion could not finish.",
    );
  });
});
