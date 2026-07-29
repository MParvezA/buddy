import { expect, test } from "@playwright/test";

test("settings stays keyboard-usable and responsive with privacy-safe diagnostics", async ({
  page,
}) => {
  await page.goto("/settings");
  await expect(
    page.getByRole("heading", { name: "Inspect and manage retained data" }),
  ).toBeVisible();
  await expect(page.getByText(/schema 007_gpt_session_briefs\.sql/)).toBeVisible();
  await expect(page.getByText(/foreign-key violations/)).toBeVisible();
  await expect(page.getByRole("link", { name: "Export JSON" })).toBeVisible();
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
  ).toBe(true);

  await page.getByRole("button", { name: "Delete all local data" }).focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("dialog", { name: "Delete all local data?" })).toBeVisible();
  await expect(page.getByLabel("Confirmation")).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Delete all local data" })).toBeFocused();

  const exported = await page.request.get("/api/operations/export");
  expect(exported.ok()).toBe(true);
  expect(exported.headers()["content-disposition"]).toContain(
    "codex-daily-export.json",
  );
  const body = await exported.text();
  expect(body).not.toMatch(
    /SECRET RESPONSE|SECRET COMMAND|SECRET QUESTION|SECRET FAILURE|SECRET BLOCKER|rawProtocol|credential/,
  );
});
test("confirmed day deletion affects local monitor data only", async ({
  page,
}, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "Exercise destructive local scope once.");
  await page.goto("/settings");
  const localDate = page.getByLabel("Retained local day");
  await localDate.fill("2026-07-29");
  await page.getByRole("button", { name: "Delete this local day" }).click();
  await expect(page.getByRole("dialog", { name: "Delete 2026-07-29?" })).toBeVisible();
  await page.getByLabel("Confirmation").fill("DELETE 2026-07-29");
  await Promise.all([
    page.waitForLoadState("domcontentloaded"),
    page.getByRole("button", { name: "Delete local data" }).click(),
  ]);
  await expect(page.getByRole("heading", { name: "Settings" })).toBeVisible();
  const observer = await page.request.get("/api/observer");
  expect(observer.ok()).toBe(true);
  expect(await observer.text()).not.toMatch(
    /thread\/delete|thread\/archive|turn\/start|SECRET COMMAND/,
  );
});
