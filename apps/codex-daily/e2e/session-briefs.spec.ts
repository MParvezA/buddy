import { expect, test } from "@playwright/test";

test("recent-session window stays literal and streams GPT-5.6 results", async ({
  page,
}, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "Exercise the live mutation once.");
  await page.goto("/");

  const section = page.getByRole("region", { name: "Recent session briefs" });
  await expect(section).toBeVisible();
  const cards = section.locator(".session-brief-card");
  await expect(cards).toHaveCount(10);
  await expect(section.getByText("10 recent")).toBeVisible();
  await expect(cards.nth(0).getByRole("heading", { name: "Observed chat" })).toBeVisible();
  await expect(
    cards.nth(1).getByRole("heading", { name: "Second observed chat" }),
  ).toBeVisible();
  await expect(
    cards.nth(9).getByRole("heading", { name: "Recent session 10" }),
  ).toBeVisible();
  await expect(section.getByText("Older active chat")).toHaveCount(0);

  const refresh = section.getByRole("button", { name: "Refresh 10 briefs" });
  await refresh.focus();
  await page.keyboard.press("Enter");
  await expect(refresh).toBeFocused();
  await expect(section.getByText("GPT-5.6 derived")).toHaveCount(10, {
    timeout: 15_000,
  });
  await expect(section.getByRole("heading", { name: "Going on" }).first()).toBeVisible();
  await expect(
    section.getByRole("heading", { name: "Chat-reported done" }).first(),
  ).toBeVisible();
  await expect(
    section.getByRole("heading", { name: "What you should do" }).first(),
  ).toBeVisible();
  await expect(section.getByRole("heading", { name: "Blockers" }).first()).toBeVisible();
  await expect(section.getByText("High confidence").first()).toBeVisible();
  await expect(section.getByText("Current").first()).toBeVisible();
  await expect(section.getByText("10 ready")).toBeVisible();

  const response = await page.request.get("/api/session-briefs");
  const body = await response.text();
  expect(body).not.toMatch(
    /SYNTHETIC_SOURCE_SECRET|SYNTHETIC_REASONING_SECRET|SECRET RESPONSE|rawProtocol|prompt|reasoning|turns/,
  );
});

test("keyboard refresh, retry, and thread navigation retain truthful controls", async ({
  page,
}, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "Exercise keyboard mutations once.");
  const failedSnapshot = {
    observer: { state: "connected", capability: "shared_live" },
    selectedAt: "2026-07-29T14:00:00.000Z",
    items: [{
      threadId: "thread-one",
      targetUpdatedAt: "2026-07-29T13:00:00.000Z",
      analysisStatus: "failed",
      freshness: "stale",
      lastGood: {
        sourceUpdatedAt: "2026-07-29T12:59:00.000Z",
        generatedAt: "2026-07-29T13:00:00.000Z",
        generator: "codex_app_server",
        modelId: "gpt-5.6-sol",
        currentState: "The chat is organizing a synthetic release.",
        done: [],
        operatorActions: ["Review the synthetic checklist."],
        blockers: [],
        confidence: "medium",
        evidence: ["user:first-intent"],
      },
      failure: { category: "timeout", at: "2026-07-29T14:00:00.000Z" },
      queuedAt: null,
      startedAt: null,
      updatedAt: "2026-07-29T14:00:00.000Z",
    }],
    total: 1,
    queued: 0,
    analyzing: 0,
    ready: 0,
    stale: 1,
    unavailable: 0,
    failed: 1,
  };
  let refreshRequests = 0;
  let retryRequests = 0;
  await page.route("**/api/session-briefs", async (route) => {
    await route.fulfill({ json: failedSnapshot });
  });
  await page.route("**/api/session-briefs/events", (route) => route.abort());
  await page.route("**/api/session-briefs/refresh", async (route) => {
    refreshRequests += 1;
    await route.fulfill({ status: 202, json: failedSnapshot });
  });
  await page.route("**/api/session-briefs/thread-one/refresh", async (route) => {
    retryRequests += 1;
    await route.fulfill({ status: 202, json: failedSnapshot });
  });
  const observed = await (await page.request.get("/api/observer")).json();
  const outcomeTitle = "Keyboard-linked outcome";
  await page.route("**/api/planning", async (route) => {
    await route.fulfill({
      json: {
        localDate: "2026-07-29",
        timezone: "Europe/Berlin",
        reviewRequired: false,
        tasks: [{
          id: "keyboard-task",
          localDate: "2026-07-29",
          title: outcomeTitle,
          clarification: null,
          position: 0,
          lifecycle: "open",
          originTaskId: null,
          createdAt: "2026-07-29T14:00:00.000Z",
          updatedAt: "2026-07-29T14:00:00.000Z",
          completedAt: null,
          closedAt: null,
        }],
        priorDay: { localDate: "2026-07-28", unresolvedTasks: [] },
      },
    });
  });
  await page.route(
    "**/api/tasks/keyboard-task/threads/thread-one",
    async (route) => {
      await route.fulfill({
        json: {
          ...observed,
          taskLinks: [{
            taskId: "keyboard-task",
            threadId: "thread-one",
            createdAt: "2026-07-29T14:01:00.000Z",
          }],
        },
      });
    },
  );

  await page.goto("/");
  const section = page.getByRole("region", { name: "Recent session briefs" });
  await expect(section.getByText("The chat is organizing a synthetic release."))
    .toBeVisible();
  await expect(section.getByText("Stale", { exact: true })).toBeVisible();
  await expect(section.getByText("GPT-5.6 analysis timed out.")).toBeVisible();

  const refresh = section.getByRole("button", { name: "Refresh 10 briefs" });
  await refresh.focus();
  await page.keyboard.press("Enter");
  await expect(refresh).toBeFocused();
  expect(refreshRequests).toBe(1);

  const retry = section.getByRole("button", { name: "Retry brief for Observed chat" });
  await retry.focus();
  await page.keyboard.press("Enter");
  await expect(retry).toBeFocused();
  expect(retryRequests).toBe(1);

  const card = section.locator(".session-brief-card").first();
  const outcomeSelect = card.getByRole("combobox");
  await outcomeSelect.focus();
  await page.keyboard.press("End");
  await page.keyboard.press("Enter");
  const linkOutcome = card.getByRole("button", { name: "Link" });
  await linkOutcome.focus();
  await page.keyboard.press("Enter");
  await expect(card.getByText(outcomeTitle)).toBeVisible();

  const threadLink = section.getByRole("link", { name: "Observed chat" });
  await threadLink.focus();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/threads\/thread-one$/);
  await expect(
    page.getByRole("heading", { level: 1, name: "Observed chat" }),
  ).toBeVisible();
});

test("stale offline briefs stay readable without 390px overflow", async ({ page }) => {
  const offlineSnapshot = {
    observer: { state: "disconnected", capability: "standalone_history" },
    selectedAt: "2026-07-29T14:00:00.000Z",
    items: [{
      threadId: "thread-one",
      targetUpdatedAt: "2026-07-29T13:00:00.000Z",
      analysisStatus: "unavailable",
      freshness: "stale",
      lastGood: {
        sourceUpdatedAt: "2026-07-29T12:59:00.000Z",
        generatedAt: "2026-07-29T13:00:00.000Z",
        generator: "codex_app_server",
        modelId: "gpt-5.6-sol",
        currentState: "A long but invented session state remains readable while disconnected.",
        done: [],
        operatorActions: [],
        blockers: [],
        confidence: "low",
        evidence: ["assistant:recent-1"],
      },
      failure: { category: "observer_unavailable", at: "2026-07-29T14:00:00.000Z" },
      queuedAt: null,
      startedAt: null,
      updatedAt: "2026-07-29T14:00:00.000Z",
    }],
    total: 1,
    queued: 0,
    analyzing: 0,
    ready: 0,
    stale: 1,
    unavailable: 1,
    failed: 0,
  };
  await page.route("**/api/session-briefs", async (route) => {
    await route.fulfill({ json: offlineSnapshot });
  });
  await page.route("**/api/session-briefs/events", (route) => route.abort());
  await page.goto("/");

  const section = page.getByRole("region", { name: "Recent session briefs" });
  await expect(section.getByText(/long but invented session state/)).toBeVisible();
  await expect(section.getByText("Low confidence")).toBeVisible();
  await expect(section.getByText("Stale", { exact: true })).toBeVisible();
  await expect(section.getByRole("button", { name: "Refresh 10 briefs" })).toBeDisabled();
  await expect(
    section.getByRole("button", { name: "Retry brief for Observed chat" }),
  ).toBeDisabled();
  await expect(section.getByText(/Retry is unavailable while Codex is disconnected/))
    .toBeVisible();

  const overflow = await page.evaluate(() => ({
    document: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    body: document.body.scrollWidth - document.body.clientWidth,
  }));
  expect(overflow.document).toBeLessThanOrEqual(0);
  expect(overflow.body).toBeLessThanOrEqual(0);
});
