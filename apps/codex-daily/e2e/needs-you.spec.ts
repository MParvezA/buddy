import { expect, test } from "@playwright/test";

test("shared-live attention appears immediately and local actions persist", async ({
  page,
}, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "Exercise local queue mutations once.");
  await page.goto("/");

  const approval = page.locator(".attention-card").filter({
    hasText: "Command approval requested",
  });
  const question = page.locator(".attention-card").filter({
    hasText: "User input requested",
  });
  await expect(approval).toBeVisible();
  await expect(question).toBeVisible();
  await expect(page.getByText("Turn failed", { exact: true })).toBeVisible();
  await expect(page.getByText("Turn interrupted", { exact: true })).toBeVisible();
  await expect(page.getByText("Explicit blocker", { exact: true })).toBeVisible();
  await expect(page.getByText("Possibly stale · lower certainty").first()).toBeVisible();

  await approval.getByRole("button", { name: "Acknowledge" }).click();
  await expect(approval).toHaveCount(0);
  await question.getByRole("button", { name: "Dismiss" }).click();
  await expect(question).toHaveCount(0);
  await page.reload();
  await expect(approval).toHaveCount(0);
  await expect(question).toHaveCount(0);

  await page
    .getByRole("link", { name: "Observed chat", exact: true })
    .first()
    .click();
  await expect(page.getByText(/Command approval requested/).first()).toBeVisible();
  await expect(page.getByText(/User input requested/).first()).toBeVisible();

  const observer = await page.request.get("/api/observer");
  const observerBody = await observer.text();
  expect(observerBody).not.toMatch(/SECRET COMMAND|SECRET QUESTION|SECRET FAILURE|SECRET BLOCKER/);
});
