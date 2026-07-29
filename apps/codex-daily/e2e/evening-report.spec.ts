import { expect, test } from "@playwright/test";

test("manual factual report remains usable and navigable at each viewport", async ({ page }) => {
  await page.goto("/");
  const report = page.locator("section[data-section-order='5']");
  await expect(report.getByRole("heading", { name: "Evening report" })).toBeVisible();
  await report.getByRole("button", { name: "Generate report" }).click();
  await expect(report.getByText("Recorded facts")).toBeVisible();
  await expect(report.getByText("Consider tomorrow")).toBeVisible();
  await expect(report.getByText("Generated interpretation")).toBeVisible();

  await report.getByRole("link", { name: /Open report history/ }).click();
  await expect(page.getByRole("heading", { name: "Report history" })).toBeVisible();
  const firstSnapshot = page.locator(".report-history-card").first();
  await expect(firstSnapshot).toContainText("snapshot");
  await firstSnapshot.click();
  await expect(page.getByText("Recorded facts")).toBeVisible();
  await expect(page.getByText("Generated interpretation")).toBeVisible();
  await expect(page.getByText(/cutoff/i).first()).toBeVisible();
});

test("report regeneration preserves history and schedule validation is visible", async ({
  page,
}, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "Exercise persistence once.");
  await page.goto("/");
  const before = await page.request.get("/api/reports");
  const beforeCount = (await before.json()).length as number;
  await page.locator("section[data-section-order='5']").getByRole("button", {
    name: "Generate report",
  }).click();
  await expect(page.locator("section[data-section-order='5']").getByText("Recorded facts")).toBeVisible();
  await page.locator("section[data-section-order='5']").getByRole("button", {
    name: "Generate report",
  }).click();
  await page.getByRole("link", { name: "Reports" }).click();
  await expect(page.locator(".report-history-card")).toHaveCount(beforeCount + 2);

  await page.getByRole("link", { name: "Settings" }).click();
  await page.getByLabel("Evening report time").fill("19:15");
  await page.getByLabel("IANA timezone").fill("America/New_York");
  await page.getByRole("button", { name: "Save report settings" }).click();
  await expect(page.getByRole("status").filter({ hasText: "Report schedule saved." })).toBeVisible();
  await page.reload();
  await expect(page.getByLabel("Evening report time")).toHaveValue("19:15");
  await expect(page.getByLabel("IANA timezone")).toHaveValue("America/New_York");

  await page.getByLabel("IANA timezone").fill("Not/AZone");
  await page.getByRole("button", { name: "Save report settings" }).click();
  await expect(page.getByRole("alert")).toContainText("IANA");
});

test("optional narrative uses the excluded reporting thread and leaves facts primary", async ({
  page,
}, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "Exercise the fake App Server reporting path once.");
  await page.goto("/settings");
  await page.getByLabel("IANA timezone").fill("Europe/Berlin");
  await page.getByLabel("Add optional Codex-generated interpretation").check();
  await page.getByRole("button", { name: "Save report settings" }).click();
  await expect(page.getByRole("status").filter({ hasText: "Report schedule saved." })).toBeVisible();
  await page.getByRole("link", { name: "Today", exact: true }).click();
  const report = page.locator("section[data-section-order='5']");
  await report.getByRole("button", { name: "Generate report" }).click();
  await expect(
    report.getByText("Generated summary from the dedicated reporting thread."),
  ).toBeVisible();
  await expect(report.getByText("Recorded facts")).toBeVisible();
  const observer = await page.request.get("/api/observer");
  expect(await observer.text()).not.toContain("codex-daily-reporting-thread");
});
