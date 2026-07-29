import { expect, test } from "@playwright/test";

test("built app preserves the daily hierarchy without horizontal overflow", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByRole("heading", { name: "Needs your attention" })).toBeVisible();
  await expect(page.getByText("Codex not connected", { exact: true })).toBeVisible();
  await expect(page.getByText("Local daily plan")).toBeVisible();

  const sectionHeadings = await page
    .locator('[data-testid="dashboard-sections"] > section > .section-heading h2')
    .allTextContents();
  expect(sectionHeadings).toEqual([
    "Needs your attention",
    "Today’s outcomes and progress",
    "Active Codex chats",
    "Recently completed work",
    "Evening-report preview",
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
  await page.getByRole("link", { name: "Onboarding refresh" }).first().click();
  await expect(page).toHaveURL(/\/threads\/onboarding-refresh$/);
  await expect(page.getByRole("heading", { name: "Onboarding refresh" })).toBeVisible();
  await expect(page.getByText(/Full chat transcripts are not retained/)).toBeVisible();

  await page.getByRole("link", { name: "Reports" }).click();
  await expect(page.getByRole("heading", { name: "Report history" })).toBeVisible();
  await expect(page.getByText("No saved reports yet")).toBeVisible();

  await page.getByRole("link", { name: "Settings" }).click();
  await expect(page.getByRole("heading", { name: "Settings" })).toBeVisible();
  await expect(page.getByText("Metadata only")).toBeVisible();

  await page.getByRole("link", { name: "Back to Today" }).click();
  await expect(page).toHaveURL("/");
  await expect(page.getByRole("heading", { name: "Needs your attention" })).toBeVisible();
});
