import { expect, test } from "@playwright/test";

test("observer discovers paginated chats, links a task, and reads detail transiently", async ({
  page,
}, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "Exercise the mutable local link once.");
  await page.goto("/");

  await expect(page.getByText("Codex connected", { exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "Observed chat" }).first()).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Second observed chat", exact: true }).first(),
  ).toBeVisible();
  await expect(page.getByText("Turn completed")).toBeVisible();
  await expect(page.getByText("Unplanned work").first()).toBeVisible();

  await page.locator("#new-outcome").fill("Connect daily work");
  await page.getByRole("button", { name: "Add outcome" }).click();
  const card = page.locator(".work-card").filter({
    has: page.getByRole("heading", { name: "Observed chat", exact: true }),
  });
  await card.getByRole("combobox").selectOption({ label: "Connect daily work" });
  await card.getByRole("button", { name: "Link" }).click();
  await expect(card.getByText("Connect daily work")).toBeVisible();
  await expect(card.getByText("Unplanned work")).toHaveCount(0);

  await card.getByRole("link", { name: "Observed chat" }).click();
  await expect(page.getByText("1 turns fetched in request memory")).toBeVisible();
  const observerResponse = await page.request.get("/api/observer");
  expect(await observerResponse.text()).not.toMatch(/SECRET RESPONSE|SECRET PREVIEW|turns/);
});
