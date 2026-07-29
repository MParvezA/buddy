import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import type { ReportSnapshot } from "../../../../src/shared/report";
import { ReportDigest } from "../../../../src/client/features/reports/ReportDigest";
import { ReportPreview } from "../../../../src/client/features/reports/ReportPreview";

const reportMocks = vi.hoisted(() => ({
  generate: vi.fn(),
}));

vi.mock("../../../../src/client/data/report-context", () => ({
  useReports: () => ({
    latest: null,
    scheduler: {
      schedule: {
        time: "18:00",
        timezone: "Europe/Berlin",
        narrativeEnabled: false,
      },
      nextRunAt: "2026-07-29T16:00:00.000Z",
      lastAutomaticRunAt: null,
      lastFailure: null,
    },
    loading: false,
    pending: false,
    error: null,
    reload: vi.fn(),
    generate: reportMocks.generate,
    retry: vi.fn(),
  }),
}));

vi.mock("../../../../src/client/data/planning-context", () => ({
  usePlanning: () => ({
    view: { localDate: "2026-07-29" },
  }),
}));

const snapshot: ReportSnapshot = {
  id: "snapshot",
  localDate: "2026-07-29",
  sequence: 1,
  trigger: "manual",
  cutoff: "2026-07-29T16:00:00.000Z",
  createdAt: "2026-07-29T16:00:00.000Z",
  factualDigest: {
    localDate: "2026-07-29",
    cutoff: "2026-07-29T16:00:00.000Z",
    planned: [
      {
        taskId: "task",
        title: "Ship the daily report",
        clarification: null,
        threadIds: ["thread"],
      },
    ],
    confirmedComplete: [],
    suggestedComplete: [],
    pending: [],
    blocked: [],
    unplannedWork: [],
    outstandingAttention: [],
    considerTomorrow: [],
  },
  narrative: {
    status: "ready",
    text: "Generated narrative",
    failure: null,
    suggestions: [
      {
        id: "suggestion",
        snapshotId: "snapshot",
        taskId: "task",
        reason: "The linked work looks complete.",
        sourceThreadIds: ["thread"],
        supersededAt: null,
      },
    ],
  },
};

describe("report components", () => {
  it("labels generated suggestions with their target task", () => {
    render(<ReportDigest snapshot={snapshot} />);
    expect(
      screen.getByText("Ship the daily report · completion suggestion"),
    ).toBeVisible();
    expect(screen.getByText("The linked work looks complete.")).toBeVisible();
  });

  it("attaches a rejection handler to manual report generation", async () => {
    const catchHandler = vi.fn(() => Promise.resolve());
    reportMocks.generate.mockReturnValueOnce({
      catch: catchHandler,
    } as unknown as Promise<void>);
    render(
      <MemoryRouter>
        <ReportPreview />
      </MemoryRouter>,
    );
    await userEvent.click(screen.getByRole("button", { name: "Generate report" }));
    expect(reportMocks.generate).toHaveBeenCalledWith("2026-07-29");
    expect(catchHandler).toHaveBeenCalledOnce();
  });
});
