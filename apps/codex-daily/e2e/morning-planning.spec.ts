import { expect, test } from "@playwright/test";

test("prior-day review unlocks a durable operator-owned morning plan", async ({
  page,
  request,
}, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "Run the mutating lifecycle once.");

  for (const title of ["Carry this work", "Schedule this work", "Close this work"]) {
    const response = await request.post("/api/planning/2026-07-28/tasks", {
      data: { title, clarification: `Historical note for ${title}` },
    });
    expect(response.ok()).toBeTruthy();
  }

  await page.goto("/");
  await expect(page.getByText("Morning review required")).toBeVisible();
  await expect(page.locator("#new-outcome")).toHaveCount(0);

  const carryCard = page.locator(".review-card").filter({ hasText: "Carry this work" });
  await expect(carryCard.getByRole("button")).toHaveText([
    "Carry forward",
    "Reschedule",
    "Close",
  ]);
  await carryCard.getByRole("button", { name: "Carry forward" }).click();

  const rescheduleCard = page.locator(".review-card").filter({ hasText: "Schedule this work" });
  await rescheduleCard.getByRole("button", { name: "Reschedule" }).click();
  await expect(rescheduleCard.getByLabel("New date")).toHaveAttribute("min", "2026-07-30");
  await rescheduleCard.getByLabel("New date").fill("2026-07-29");
  await expect(rescheduleCard.getByRole("button", { name: "Save new date" })).toBeDisabled();
  await rescheduleCard.getByLabel("New date").fill("2026-08-04");
  await rescheduleCard.getByRole("button", { name: "Save new date" }).click();

  const closeCard = page.locator(".review-card").filter({ hasText: "Close this work" });
  await closeCard.getByRole("button", { name: "Close" }).click();

  await expect(page.getByText("Morning review required")).toHaveCount(0);
  await expect(page.locator("#new-outcome")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Carry this work", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Schedule this work", exact: true })).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Close this work", exact: true })).toHaveCount(0);

  await page.locator("#new-outcome").fill("Publish the daily monitor");
  await page.getByLabel("Clarification (optional)").fill("Include a useful pending-work view");
  await page.getByRole("button", { name: "Add outcome" }).click();
  await expect(page.getByRole("button", { name: "Add outcome" })).toBeEnabled();
  await page.locator("#new-outcome").fill("Verify the local workflow");
  await page.getByRole("button", { name: "Add outcome" }).click();
  await expect(page.getByRole("button", { name: "Add outcome" })).toBeEnabled();

  const publish = page.locator(".durable-outcome").filter({ hasText: "Publish the daily monitor" });
  await publish.getByRole("button", { name: "Edit" }).click();
  await page
    .getByLabel("Clarification", { exact: true })
    .fill("Include pending work and morning decisions");
  await page.getByRole("button", { name: "Save changes" }).click();
  await expect(publish.getByText("Include pending work and morning decisions")).toBeVisible();

  await page
    .getByRole("button", { name: "Move Verify the local workflow up" })
    .click();
  const titles = await page.locator(".durable-outcome h3").allTextContents();
  expect(titles.indexOf("Verify the local workflow")).toBeLessThan(
    titles.indexOf("Publish the daily monitor"),
  );

  await publish.getByRole("button", { name: "Confirm complete" }).click();
  await expect(publish.getByText("Operator confirmed complete")).toBeVisible();
  await publish.getByRole("button", { name: "Reopen outcome" }).click();
  await expect(publish.getByText("Open", { exact: true })).toBeVisible();

  await page.reload();
  await expect(page.getByText("Publish the daily monitor")).toBeVisible();
  await expect(page.getByText("Include pending work and morning decisions")).toBeVisible();
  await expect(page.getByText("Operator confirmed complete")).toHaveCount(0);

  const future = await request.get("/api/planning?date=2026-08-04");
  const futureView = await future.json();
  expect(futureView.tasks).toEqual([
    expect.objectContaining({
      title: "Schedule this work",
      lifecycle: "open",
      originTaskId: expect.any(String),
    }),
  ]);
});
