import { expect, test } from "@playwright/test";

test("built app preserves the daily hierarchy without horizontal overflow", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByRole("heading", { name: "Needs your attention" })).toBeVisible();
  await expect(page.getByText("Codex connected", { exact: true })).toBeVisible();
  await expect(page.getByText("Local daily monitor")).toBeVisible();

  const sectionHeadings = await page
    .locator('[data-testid="dashboard-sections"] > section > .section-heading h2')
    .allTextContents();
  expect(sectionHeadings).toEqual([
    "Needs your attention",
    "Today’s outcomes and progress",
    "Recent session briefs",
    "Recently completed work",
    "Evening report",
  ]);

  const overflow = await page.evaluate(() => ({
    document: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    body: document.body.scrollWidth - document.body.clientWidth,
  }));
  expect(overflow.document).toBeLessThanOrEqual(0);
  expect(overflow.body).toBeLessThanOrEqual(0);
});

test("built app routes through thread, report, settings, and back to Today", async ({ page }) => {
  await page.goto("/");
  await page
    .getByRole("link", { name: "Observed chat", exact: true })
    .first()
    .click();
  await expect(page).toHaveURL(/\/threads\/thread-one$/);
  await expect(
    page
      .locator("article.secondary-page")
      .getByRole("heading", { level: 1, name: "Observed chat", exact: true }),
  ).toBeVisible();
  await expect(page.getByText(/Full history is fetched from Codex/)).toBeVisible();

  await page.getByRole("link", { name: "Reports" }).click();
  await expect(page.getByRole("heading", { name: "Report history" })).toBeVisible();

  await page.getByRole("link", { name: "Settings" }).click();
  await expect(page.getByRole("heading", { name: "Settings" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Metadata and snapshots" })).toBeVisible();

  await page.getByRole("link", { name: "Back to Today" }).click();
  await expect(page).toHaveURL("/");
  await expect(page.getByRole("heading", { name: "Needs your attention" })).toBeVisible();
});

test("disconnected monitoring keeps planning and report history usable", async ({
  page,
}) => {
  const retainedThread = {
    id: "retained-thread",
    sessionId: "retained-session",
    title: "Retained offline work",
    cwd: "/workspace/retained",
    source: "cli",
    cliVersion: "0.146.0",
    createdAt: "2026-07-29T10:00:00.000Z",
    updatedAt: "2026-07-29T10:00:00.000Z",
    recencyAt: "2026-07-29T10:00:00.000Z",
    archived: false,
    lastObservedAt: "2026-07-29T10:00:00.000Z",
    runtime: "unknown",
    waitingOnApproval: false,
    waitingOnUserInput: false,
    lastActivityAt: "2026-07-29T10:00:00.000Z",
  };
  const retainedActivity = {
    sourceKey: "turn:retained-thread:turn-one:failed",
    threadId: "retained-thread",
    turnId: "turn-one",
    itemId: null,
    occurredAt: "2026-07-29T10:00:00.000Z",
    category: "turn",
    lifecycle: "failed",
    label: "Retained offline failure",
  };
  await page.route("**/api/observer", async (route) => {
    await route.fulfill({
      json: {
        health: {
          state: "disconnected",
          capability: "shared_live",
          lastSuccessfulSyncAt: "2026-07-29T10:00:00.000Z",
          lastInventoryRefreshAt: "2026-07-29T10:00:00.000Z",
          diagnostic: "Codex is temporarily unavailable.",
        },
        threads: [retainedThread],
        activities: [retainedActivity],
        taskLinks: [],
      },
    });
  });
  await page.route(
    "**/api/observer/threads/retained-thread",
    async (route) => {
      await route.fulfill({
        headers: { "cache-control": "no-store" },
        json: {
          thread: retainedThread,
          activities: [retainedActivity],
          transientHistory: {
            status: "unavailable",
            reason: "Codex is disconnected; full history is unavailable.",
          },
        },
      });
    },
  );
  await page.route("**/api/observer/events", (route) => route.abort());
  await page.route("**/api/attention", async (route) => {
    await route.fulfill({
      json: {
        capability: "shared_live",
        connectionState: "disconnected",
        liveRequestCoverage: "available",
        items: [],
      },
    });
  });
  await page.route("**/api/attention/events", (route) => route.abort());
  await page.route("**/api/session-briefs", async (route) => {
    await route.fulfill({
      json: {
        observer: { state: "disconnected", capability: "shared_live" },
        selectedAt: "2026-07-29T10:00:00.000Z",
        items: [{
          threadId: "retained-thread",
          targetUpdatedAt: "2026-07-29T10:00:00.000Z",
          analysisStatus: "unavailable",
          freshness: "missing",
          lastGood: null,
          failure: {
            category: "observer_unavailable",
            at: "2026-07-29T10:00:00.000Z",
          },
          queuedAt: null,
          startedAt: null,
          updatedAt: "2026-07-29T10:00:00.000Z",
        }],
        total: 1,
        queued: 0,
        analyzing: 0,
        ready: 0,
        stale: 0,
        unavailable: 1,
        failed: 0,
      },
    });
  });
  await page.route("**/api/session-briefs/events", (route) => route.abort());

  await page.goto("/");
  await expect(page.getByText("Codex disconnected", { exact: true })).toBeVisible();
  await expect(page.getByText(/last-known queue/)).toBeVisible();
  await expect(
    page.getByRole("region", { name: "Today’s outcomes and progress" }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Retained offline work" }).click();
  await expect(
    page.getByRole("heading", { name: "Retained offline work", level: 1 }),
  ).toBeVisible();
  await expect(page.getByText(/Retained offline failure/)).toBeVisible();
  await expect(
    page.getByText("Codex is disconnected; full history is unavailable."),
  ).toBeVisible();
  await page.getByRole("link", { name: "Back to Today" }).click();
  await page.getByRole("link", { name: "Reports" }).click();
  await expect(page.getByRole("heading", { name: "Report history" })).toBeVisible();
});
